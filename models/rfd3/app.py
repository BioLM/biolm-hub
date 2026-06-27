"""Modal app for RFdiffusion3.

RFdiffusion3 is an all-atom generative diffusion model for biomolecular structure design.
Based on RosettaCommons/foundry implementation (BSD 3-Clause License).
"""

import json
import os
import tempfile
from pathlib import Path

import modal

from models.commons.billing.mixin import BillingMixinSnap
from models.commons.core.decorator import modal_endpoint
from models.commons.core.error import UserError
from models.commons.modal.downloader import setup_download_layer
from models.commons.modal.source import setup_source_layer
from models.commons.model.config import biolm_model_class
from models.commons.util.config import (
    cloudflare_r2_secret,
    common_requirements,
    redis_url_secret,
)
from models.commons.util.device import get_torch_device
from models.rfd3.config import MODEL_FAMILY
from models.rfd3.download import get_model_dir
from models.rfd3.schema import (
    RFD3DesignRequest,
    RFD3DesignResponse,
    RFD3DesignResponseResult,
    RFD3Params,
)

# Build Modal container image with Python 3.12 (foundry requires >=3.12)
# Using micromamba for proper Python 3.12 setup
image = modal.Image.micromamba(python_version="3.12")

# Clone foundry repository at specific commit
# Repository: https://github.com/RosettaCommons/foundry
# Commit: 6866d610a9d5e485ef4bf601adb40c4928b8321f (latest as of implementation)
foundry_src = "/root/foundry"
foundry_commit = "6866d610a9d5e485ef4bf601adb40c4928b8321f"

# Install foundry dependencies (matching RF3's approach)
image = (
    image.apt_install("procps", "git", "build-essential", "wget")
    .run_commands(
        f"git clone https://github.com/RosettaCommons/foundry.git {foundry_src}",
        f"cd {foundry_src} && git checkout {foundry_commit}",
    )
    .uv_pip_install(common_requirements)
    .uv_pip_install(
        # Core ML dependencies (pinned to known-working versions)
        "torch==2.7.1",
        "lightning==2.6.0",
        "loralib==0.1.2",
        "einops==0.8.2",
        "einx==0.3.0",
        "opt_einsum==3.4.0",
        "dm-tree==0.1.9",
        "atomworks[ml]==2.2.0",
        # Config & CLI
        "rootutils==1.0.7",
        "hydra-core==1.3.2",
        "environs==11.2.1",
        # Logging
        "wandb==0.24.0",
        "rich==14.3.1",
        # Typing
        "jaxtyping==0.3.6",
        "beartype==0.22.9",
        "typer==0.21.1",
        # Utilities
        "zstandard==0.25.0",
        "toolz==1.1.0",
        "pandas==2.3.3",
    )
    # Install foundry as regular package (not editable) to get the CLI
    # First, remove/fix broken symlinks that cause build issues
    .run_commands(
        f"cd {foundry_src} && find . -type l -xtype l -delete",  # Remove broken symlinks
        f"cd {foundry_src} && pip install .",
    )
)

# Set PYTHONPATH to include foundry
image = image.env({"PYTHONPATH": f"{foundry_src}:$PYTHONPATH"})

# Setup download layer with model weights (runs after foundry CLI is available)
image = setup_download_layer(
    image,
    base_model_slug=RFD3Params.base_model_slug,
    params_version=RFD3Params.params_version,
    variant_config=None,  # no variants
)

# Finally, add all model files
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)

# Define the app using unified config
app_name, modal_resource_spec = MODEL_FAMILY.get_app_config()
print(f"App name: {app_name}")
app = modal.App(app_name, image=image)


@app.cls(
    image=image,
    secrets=[cloudflare_r2_secret, redis_url_secret],
    enable_memory_snapshot=True,
    experimental_options={"enable_gpu_snapshot": True},
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class RFD3Model(BillingMixinSnap):
    app_username: str = modal.parameter(default="default_user")

    @modal.enter(snap=True)
    def setup_model(self):
        """Load RFdiffusion3 model on GPU for GPU memory snapshot."""
        import torch

        print("🚀 Loading RFdiffusion3 model on GPU for GPU memory snapshot...")

        # Set deterministic behavior
        torch.manual_seed(42)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42)

        self.torch = torch
        self.model_dir = get_model_dir()

        print(f"🔍 RFD3 model directory: {self.model_dir}")

        # Set up environment for foundry
        os.environ["PROJECT_ROOT"] = str(Path(__file__).parent.parent.parent)

        # Get device
        self.device = get_torch_device()

        # Determine checkpoint path (downloaded as rfd3_latest.ckpt by foundry CLI)
        self.ckpt_path = self.model_dir / "rfd3_latest.ckpt"

        if self.ckpt_path.exists():
            print(f"✅ Found RFD3 checkpoint at {self.ckpt_path}")
        else:
            print(f"ℹ️ Checkpoint will be downloaded to: {self.ckpt_path}")

        # Import RFD3 inference engine from foundry
        try:
            from rfd3.engine import RFD3InferenceConfig, RFD3InferenceEngine

            self.RFD3InferenceEngine = RFD3InferenceEngine
            self.RFD3InferenceConfig = RFD3InferenceConfig

            # Create inference engine configuration
            # We'll initialize the full engine on first request to save startup time
            self.engine_config = {
                "ckpt_path": str(self.model_dir / "rfd3_latest.ckpt"),
                "diffusion_batch_size": 1,  # Will be overridden per request
                "skip_existing": False,
                "json_keys_subset": None,
                "specification": {},
                "inference_sampler": {},
                "cleanup_guideposts": True,
                "cleanup_virtual_atoms": True,
                "read_sequence_from_sequence_head": True,
                "output_full_json": True,
                "dump_prediction_metadata_json": True,
                "dump_trajectories": False,
                "align_trajectory_structures": False,
                "prevalidate_inputs": True,
                "low_memory_mode": False,
                "num_nodes": 1,
                "devices_per_node": 1,
                "verbose": True,
                "seed": None,
            }

            print("✅ RFdiffusion3 dependencies loaded successfully")
        except ImportError as e:
            print(f"⚠️ Warning: Could not import foundry/rfd3: {e}")
            print("    This may be expected if foundry is not yet installed")
            # Don't raise here - just log the warning

        print(f"✅ RFD3 model setup complete on {self.device}")

        # Cache to R2 at runtime if checkpoint was just downloaded (not in R2)
        # This ensures future builds can use R2 cache
        self._cache_to_r2_if_needed()

    def _cache_to_r2_if_needed(self):
        """Cache model weights to R2 at runtime if they were downloaded via foundry CLI.

        This runs after setup_model() to avoid blocking image builds.
        Only caches if checkpoint exists and R2 doesn't already have it.
        """
        if not self.ckpt_path.exists():
            return

        try:
            from models.commons.storage.r2_utils import R2Utils
            from models.commons.util.config import r2_bucket_name
            from models.rfd3.schema import RFD3Params

            r2_prefix = (
                f"model-store/{RFD3Params.base_model_slug}/{RFD3Params.params_version}"
            )

            # Check if already in R2 (quick check)
            from models.commons.storage.r2 import get_r2_client

            r2_client = get_r2_client()
            manifest_key = f"{r2_prefix}/.r2_manifest.json"

            try:
                r2_client.head_object(Bucket=r2_bucket_name, Key=manifest_key)
                print(f"✅ Model already cached in R2 at {r2_prefix}")
                return
            except Exception:
                # Not in R2, proceed with upload
                pass

            print(
                f"📤 Caching checkpoint to R2 at {r2_prefix} (runtime, non-blocking)..."
            )
            success = R2Utils.upload_to_r2_atomic(
                source_dir=self.model_dir,
                r2_prefix=r2_prefix,
                bucket_name=r2_bucket_name,
                create_manifest=True,
            )
            if success:
                print("✅ Cached to R2 successfully - future builds will use R2 cache")
            else:
                print("⚠️ Failed to cache to R2 (non-fatal)")
        except Exception as e:
            print(f"⚠️ Failed to cache to R2 (non-fatal): {e}")

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def generate(self, payload: RFD3DesignRequest) -> RFD3DesignResponse:  # noqa: C901
        """
        Performs structure generation/design using RFdiffusion3.

        Args:
            payload: Design request with parameters and input components

        Returns:
            Design response with generated structures
        """
        params = payload.params
        item = payload.items[0]  # Batch size fixed to 1

        print(f"🎨 Starting RFdiffusion3 design for '{item.name}'")
        print(f"   Components: {len(item.components)}")
        print(f"   Diffusion steps: {params.num_diffusion_steps}")
        print(f"   Batch size: {params.diffusion_batch_size}")

        # Create temporary directory for all files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)

            # Handle input structure file if provided
            # First check if any component has structure_cif (CIF string)
            structure_cif_from_component = None
            for comp in item.components:
                if comp.structure_cif:
                    structure_cif_from_component = comp.structure_cif
                    break

            if structure_cif_from_component:
                # Write CIF string to temp file
                temp_input_path = temp_dir_path / "input_structure.cif"
                with open(temp_input_path, "w") as f:
                    f.write(structure_cif_from_component)
                print(f"✅ Wrote structure_cif to temp file: {temp_input_path}")

                # Update the specification to use the temp path
                item_copy = item.model_copy()
                item_copy.input_structure_path = str(temp_input_path)
            elif item.input_structure_path:
                # Local file path only (URLs should be downloaded client-side)
                input_path = Path(item.input_structure_path)

                # Validate path exists and is a file
                if not input_path.exists():
                    raise UserError(
                        f"Input structure file not found: {item.input_structure_path}"
                    )
                if not input_path.is_file():
                    raise UserError(
                        f"Input structure path is not a file: {item.input_structure_path}"
                    )

                # Validate file extension
                valid_extensions = {".pdb", ".cif", ".mmcif"}
                if input_path.suffix.lower() not in valid_extensions:
                    raise UserError(
                        f"Input structure file must have extension .pdb, .cif, or .mmcif, got: {input_path.suffix}"
                    )

                # Copy to temp directory with original name
                import shutil

                temp_input_path = temp_dir_path / input_path.name
                shutil.copy2(input_path, temp_input_path)

                # Update the specification to use the temp path
                item_copy = item.model_copy()
                item_copy.input_structure_path = str(temp_input_path)
            else:
                item_copy = item

            # Convert input to JSON format expected by RFD3
            design_spec = self._create_design_specification(item_copy, params)

            # Write design specification to JSON file
            input_json_path = temp_dir_path / "design_input.json"
            with open(input_json_path, "w") as f:
                json.dump(design_spec, f, indent=2)

            print(f"✅ Created design specification at: {input_json_path}")

            # Create output directory
            output_dir = temp_dir_path / "output"
            output_dir.mkdir()

            # Create inference engine
            try:
                # Check if RFD3InferenceEngine is available
                if not hasattr(self, "RFD3InferenceEngine"):
                    raise UserError(
                        "RFD3 inference engine not available. "
                        "Foundry library may not be installed correctly. "
                        "This is expected during initial setup before foundry integration is complete."
                    )

                # Update engine config with request-specific parameters
                engine_config = self.engine_config.copy()
                engine_config["diffusion_batch_size"] = params.diffusion_batch_size
                engine_config["dump_trajectories"] = params.include_trajectories
                engine_config["seed"] = params.seed

                # Enable low_memory_mode to reduce GPU memory usage (helps with smaller GPUs)
                # This uses chunked P_LL computation which is more memory efficient
                engine_config["low_memory_mode"] = True

                # Override inference sampler with request parameters
                inference_sampler = {
                    "num_steps": params.num_diffusion_steps,
                    "temperature": params.temperature,
                }

                # Add optional advanced sampling parameters
                if params.step_scale is not None:
                    inference_sampler["step_scale"] = params.step_scale
                if params.noise_scale is not None:
                    inference_sampler["noise_scale"] = params.noise_scale
                if params.center_option is not None:
                    inference_sampler["center_option"] = params.center_option

                engine_config["inference_sampler"] = inference_sampler

                # Create engine
                engine = self.RFD3InferenceEngine(
                    **self.RFD3InferenceConfig(**engine_config)
                )

                # Run inference
                print("🔄 Running RFdiffusion3 inference...")
                outputs = engine.run(
                    inputs=str(input_json_path),
                    n_batches=None,
                    out_dir=str(output_dir),
                )

                print("✅ RFdiffusion3 inference completed")

            except Exception as e:
                print(f"❌ RFdiffusion3 inference failed: {e}")
                raise UserError(f"RFdiffusion3 inference failed: {str(e)}") from e

            # Process outputs
            results = []

            # Debug: Check what outputs contains
            print(f"🔍 Output type: {type(outputs)}, value: {outputs}")

            # Check if outputs is a list (direct output) or dict (in-memory mode)
            if isinstance(outputs, list):
                # Outputs is a list of results directly
                print(f"📦 Processing {len(outputs)} outputs from list")
                for output in outputs:
                    result = self._process_output(output, params)
                    results.append(result)
            elif isinstance(outputs, dict):
                # If outputs returned as dict (in-memory mode)
                print(f"📦 Processing outputs from dict with {len(outputs)} keys")
                for _example_id, output_list in outputs.items():
                    for output in output_list:
                        result = self._process_output(output, params)
                        results.append(result)
            elif outputs is None:
                # Outputs were written to disk (engine.run returns None when writing to disk)
                print("📦 Outputs written to disk, searching for files...")
            else:
                # Outputs were written to disk (engine.run returns None when writing to disk)
                print(f"📦 Outputs type {type(outputs)} - assuming written to disk")

            # If no results yet, check disk
            if not results:
                # Outputs were written to disk
                # Find all generated CIF files in output directory (recursively, as they may be in subdirectories)
                print(f"🔍 Searching for CIF files in {output_dir}...")
                cif_files = sorted(output_dir.rglob("*.cif.gz"))

                if not cif_files:
                    # Also check for uncompressed CIF files
                    print(
                        "🔍 No compressed CIF files found, checking for uncompressed..."
                    )
                    cif_files = sorted(output_dir.rglob("*.cif"))

                if not cif_files:
                    # List what files actually exist for debugging
                    all_files = list(output_dir.rglob("*"))
                    print("❌ No CIF files found. Files in output directory:")
                    for f in all_files[:20]:  # Show first 20 files
                        print(f"   {f}")
                    if len(all_files) > 20:
                        print(f"   ... and {len(all_files) - 20} more files")
                    raise UserError(
                        f"No structures generated. Checked {output_dir} for *.cif.gz and *.cif files. "
                        "Check input parameters and try again."
                    )

                print(f"🔍 Found {len(cif_files)} generated structures")

                import gzip

                for cif_path in cif_files[: params.diffusion_batch_size]:
                    # Read CIF file (handle both compressed and uncompressed)
                    if cif_path.suffix == ".gz":
                        with gzip.open(cif_path, "rt") as f:
                            cif_content = f.read()
                    else:
                        with open(cif_path) as f:
                            cif_content = f.read()

                    # Check for trajectory
                    trajectory_cif = None
                    if params.include_trajectories:
                        # Try compressed trajectory first
                        traj_path = (
                            cif_path.parent / f"{cif_path.stem}_trajectory.cif.gz"
                        )
                        if not traj_path.exists():
                            # Try uncompressed
                            traj_path = (
                                cif_path.parent / f"{cif_path.stem}_trajectory.cif"
                            )
                        if traj_path.exists():
                            if traj_path.suffix == ".gz":
                                with gzip.open(traj_path, "rt") as f:
                                    trajectory_cif = f.read()
                            else:
                                with open(traj_path) as f:
                                    trajectory_cif = f.read()

                    result = RFD3DesignResponseResult(
                        structure_cif=cif_content,
                        trajectory_cif=trajectory_cif,
                    )
                    results.append(result)

            print(f"✅ Processed {len(results)} design results")

            # Ensure we have at least some results
            if not results:
                raise UserError(
                    f"No structures generated. Checked {output_dir} for *.cif.gz and *.cif files. "
                    "Check input parameters and try again."
                )

        # Always return a response with results (even if empty, though we check above)
        return RFD3DesignResponse(results=[results])

    def _create_design_specification(self, item, params):  # noqa: C901
        """Convert API input to RFD3 design specification JSON format.

        Supports:
        - Unconditional design (length only)
        - Motif scaffolding (input structure + fixed residues)
        - Partial diffusion (input structure + partial_t)
        - Binder design (input structure + target chain)
        """
        spec = {}

        # Handle input structure file
        if item.input_structure_path:
            spec["input"] = item.input_structure_path

        # Handle length constraint
        if item.length:
            spec["length"] = item.length
        else:
            # Calculate total length from components if no explicit length
            total_length = 0
            for comp in item.components:
                if comp.sequence:
                    total_length += len(comp.sequence)
            if total_length > 0:
                spec["length"] = total_length

        # Handle contig specification
        if item.contig:
            spec["contig"] = item.contig

        # Handle unindexed motifs
        if item.unindex:
            if isinstance(item.unindex, list):
                spec["unindex"] = ",".join(item.unindex)
            else:
                spec["unindex"] = item.unindex

        # Handle ligands
        if item.ligands:
            spec["ligand"] = ",".join(item.ligands)
            # By default, ligands are fixed, but we can explicitly fix them via select_fixed_atoms
            # This ensures ligands cofold with the protein

        # Handle fixed atoms/residues
        # Convert fixed_residues to select_fixed_atoms format (foundry uses "A100-130": "ALL")
        fixed_atoms_dict = {}

        # Process fixed_residues from components
        for comp in item.components:
            if comp.fixed_residues:
                chain_id = comp.chain_id or "A"
                for residue_spec in comp.fixed_residues:
                    # Handle formats:
                    # - "A/100-130" or "A100-130" -> "A100-130": "ALL"
                    # - "100-130" -> "A100-130": "ALL" (use component's chain_id)
                    # - "A/100" or "A100" -> "A100": "ALL"
                    # - "100" -> "A100": "ALL"

                    # Remove any slashes and extract chain/residue
                    residue_spec_clean = residue_spec.replace("/", "")

                    # Check if it starts with a letter (chain ID)
                    if residue_spec_clean and residue_spec_clean[0].isalpha():
                        # Has chain ID: "A100-130" or "A100"
                        key = residue_spec_clean
                    else:
                        # No chain ID: "100-130" or "100", use component's chain
                        key = f"{chain_id}{residue_spec_clean}"

                    # Foundry format: "A100-130": "ALL" (fixes all atoms in residue/range)
                    fixed_atoms_dict[key] = "ALL"

            # Process fixed_atoms from components (specific atoms to fix)
            if comp.fixed_atoms:
                chain_id = comp.chain_id or "A"
                for atom_spec in comp.fixed_atoms:
                    # Handle formats:
                    # - "A/ALA/10/CA" or "A/10/CA" -> "A10": "CA"
                    # - "10/CA" -> "A10": "CA" (use component's chain_id)

                    parts = [
                        p for p in atom_spec.split("/") if p
                    ]  # Remove empty strings

                    if len(parts) >= 2:
                        # Last part is atom name
                        atom_name = parts[-1]

                        # Second-to-last or first is residue number
                        if parts[0][0].isalpha():
                            # Format: "A/10/CA" or "A/ALA/10/CA"
                            chain = parts[0]
                            resnum = parts[1] if len(parts) > 2 else parts[-2]
                        else:
                            # Format: "10/CA" - use component's chain
                            chain = chain_id
                            resnum = parts[0]

                        key = f"{chain}{resnum}"

                        # Add atom to the list for this residue
                        if key not in fixed_atoms_dict:
                            fixed_atoms_dict[key] = []
                        if not isinstance(fixed_atoms_dict[key], list):
                            # Convert existing string to list
                            fixed_atoms_dict[key] = [fixed_atoms_dict[key]]
                        fixed_atoms_dict[key].append(atom_name)

        # Convert list values to comma-separated strings
        for key, value in fixed_atoms_dict.items():
            if isinstance(value, list):
                fixed_atoms_dict[key] = ",".join(value)

        # Ensure ligands are fixed (cofolded) if specified
        # By default foundry fixes ligands, but we explicitly set it to ensure cofolding
        if item.ligands:
            for ligand in item.ligands:
                # Fix all atoms of the ligand to ensure it cofolds with the protein
                # Use "ALL" to fix all atoms
                if ligand not in fixed_atoms_dict:
                    fixed_atoms_dict[ligand] = "ALL"

        if fixed_atoms_dict:
            spec["select_fixed_atoms"] = fixed_atoms_dict

        # Handle partial diffusion
        if item.partial_t is not None:
            spec["partial_t"] = item.partial_t

        # Handle motif selection
        if item.motif_selection:
            spec["motif_selection"] = item.motif_selection

        # Handle target chain for binder design
        if item.target_chain:
            spec["target_chain"] = item.target_chain

        # RFD3 expects a dictionary with example IDs as keys
        return {item.name: spec}

    def _process_output(self, output, params):
        """Process an RFD3Output object into API response format."""
        import io

        from atomworks.io.utils.io_utils import to_cif_file

        # Convert atom array to CIF string
        cif_buffer = io.StringIO()
        to_cif_file(
            output.atom_array,
            cif_buffer,
            file_type="cif",
            include_entity_poly=False,
        )
        cif_content = cif_buffer.getvalue()

        # Handle trajectories if requested
        trajectory_cif = None
        if params.include_trajectories and hasattr(output, "denoised_trajectory_stack"):
            if output.denoised_trajectory_stack is not None:
                traj_buffer = io.StringIO()
                to_cif_file(
                    output.denoised_trajectory_stack,
                    traj_buffer,
                    file_type="cif",
                    include_entity_poly=False,
                )
                trajectory_cif = traj_buffer.getvalue()

        return RFD3DesignResponseResult(
            structure_cif=cif_content,
            trajectory_cif=trajectory_cif,
        )


if __name__ == "__main__":
    """
    Usage:
        python models/rfd3/app.py

        # Force deploy to "qa" or "main" environment:
        python models/rfd3/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        RFD3Model,
        description=f"Run and optionally deploy the {RFD3Params.display_name} Modal app.",
    )
