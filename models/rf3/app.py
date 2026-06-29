"""Modal app for RosettaFold3 (RF3).

RosettaFold3 is an all-atom biomolecular structure prediction network.
Based on RosettaCommons/foundry implementation (BSD 3-Clause License).
"""

import gzip
import json
import os
import tempfile
from pathlib import Path

import modal
import numpy as np

from models.commons.core.decorator import modal_endpoint
from models.commons.core.error import ServerError
from models.commons.core.logging import get_logger
from models.commons.modal.downloader import setup_download_layer
from models.commons.modal.source import setup_source_layer
from models.commons.model.base import ModelMixinSnap
from models.commons.model.config import biolm_model_class
from models.commons.util.config import (
    cloudflare_r2_secret,
    common_requirements,
)
from models.commons.util.device import get_torch_device
from models.rf3.config import MODEL_FAMILY
from models.rf3.download import get_model_dir
from models.rf3.schema import (
    RF3ConfidenceScores,
    RF3Params,
    RF3PredictRequest,
    RF3PredictResponse,
    RF3PredictResponseResult,
)

logger = get_logger(__name__)

# Build Modal container image with Python 3.12 (foundry requires >=3.12)
# Using micromamba for proper Python 3.12 setup
image = modal.Image.micromamba(python_version="3.12")

# Setup download layer with model weights
image = setup_download_layer(
    image,
    base_model_slug=RF3Params.base_model_slug,
    weights_version=RF3Params.weights_version,
    variant_config=None,  # no variants
)

# Clone foundry repository at specific commit
# Repository: https://github.com/RosettaCommons/foundry
# Commit: 6866d610a9d5e485ef4bf601adb40c4928b8321f (latest as of implementation)
foundry_src = "/root/foundry"
foundry_commit = "6866d610a9d5e485ef4bf601adb40c4928b8321f"

# Install foundry dependencies following their exact pyproject.toml
# See: https://github.com/RosettaCommons/foundry/blob/main/pyproject.toml
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
    .uv_pip_install(
        # RF3-specific dependencies (cuequivariance for linux)
        "cuequivariance_ops_cu12==0.6.1",
        "cuequivariance_ops_torch_cu12==0.6.1",
        "cuequivariance_torch==0.6.1",
    )
    # Install foundry as regular package (not editable) to get the RF3 modules
    # First, remove/fix broken symlinks that cause build issues
    .run_commands(
        f"cd {foundry_src} && find . -type l -xtype l -delete",  # Remove broken symlinks
        f"cd {foundry_src} && pip install .",
    )
)

# Set PYTHONPATH to include foundry
image = image.env({"PYTHONPATH": f"{foundry_src}:$PYTHONPATH"})

# Finally, add all model files
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)

# Define the app using unified config
app_name, modal_resource_spec = MODEL_FAMILY.get_app_config()
logger.info("App name: %s", app_name)
app = modal.App(app_name, image=image)


@app.cls(
    image=image,
    secrets=[cloudflare_r2_secret],
    enable_memory_snapshot=True,
    experimental_options={"enable_gpu_snapshot": True},
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class RF3Model(ModelMixinSnap):
    app_username: str = modal.parameter(default="default_user")

    @modal.enter(snap=True)
    def setup_model(self):
        """Load RosettaFold3 model on GPU for GPU memory snapshot."""
        import torch

        logger.info("Loading RosettaFold3 model on GPU for GPU memory snapshot...")

        # Set deterministic behavior
        torch.manual_seed(42)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42)

        self.torch = torch
        self.model_dir = get_model_dir()

        logger.info("RF3 model directory: %s", self.model_dir)

        # Set up environment for foundry
        os.environ["PROJECT_ROOT"] = str(Path(__file__).parent.parent.parent)

        # Get device
        self.device = get_torch_device()

        # Determine checkpoint path
        self.ckpt_path = self.model_dir / "rf3_foundry_01_24_latest.ckpt"

        if self.ckpt_path.exists():
            logger.info("Found RF3 checkpoint at %s", self.ckpt_path)
        else:
            logger.info("Checkpoint will be downloaded to: %s", self.ckpt_path)

        # Import RF3 inference engine from foundry — let ImportError surface immediately
        # so a misconfigured container fails at load rather than at the first request.
        from rf3.inference_engines.rf3 import RF3InferenceEngine

        self.RF3InferenceEngine = RF3InferenceEngine
        logger.info("RosettaFold3 dependencies loaded successfully")
        logger.info("RF3 model setup complete on %s", self.device)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def fold(self, payload: RF3PredictRequest) -> RF3PredictResponse:  # noqa: C901
        """
        Performs structure prediction using RosettaFold3.

        Args:
            payload: Prediction request with parameters and input components

        Returns:
            Prediction response with predicted structures and confidence scores
        """
        params = payload.params
        item = payload.items[0]  # Batch size fixed to 1

        logger.info("Starting RosettaFold3 prediction for '%s'", item.name)
        logger.info("Components: %s", len(item.components))
        logger.info("Recycles: %s", params.n_recycles)
        logger.info("Diffusion steps: %s", params.num_steps)
        logger.info("Diffusion batch size: %s", params.diffusion_batch_size)

        # Create temporary directory for all files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)

            # Convert input to JSON format expected by RF3
            input_spec = self._create_input_specification(item, params, temp_dir_path)

            # Write input specification to JSON file
            input_json_path = temp_dir_path / "input.json"
            with open(input_json_path, "w") as f:
                json.dump(input_spec, f, indent=2)

            logger.info("Created input specification at: %s", input_json_path)

            # Create output directory
            output_dir = temp_dir_path / "output"
            output_dir.mkdir()

            # Create inference engine and run prediction
            try:
                # Create RF3 inference engine with init parameters only
                engine = self.RF3InferenceEngine(
                    ckpt_path=str(self.ckpt_path) if self.ckpt_path else None,
                    n_recycles=params.n_recycles,
                    num_steps=params.num_steps,
                    diffusion_batch_size=params.diffusion_batch_size,
                    seed=params.seed,
                    early_stopping_plddt_threshold=params.early_stopping_plddt_threshold,
                    # Note: one_model_per_file and annotate_b_factor_with_plddt go in run()
                )

                # Run inference with run() parameters
                logger.info("Running RosettaFold3 inference...")
                engine.run(
                    inputs=str(input_json_path),
                    out_dir=str(output_dir),
                    dump_predictions=True,
                    dump_trajectories=False,
                    one_model_per_file=params.one_model_per_file,
                    annotate_b_factor_with_plddt=params.annotate_b_factor_with_plddt,
                    skip_existing=False,
                    template_selection=params.template_selection,
                    ground_truth_conformer_selection=params.ground_truth_conformer_selection,
                    cyclic_chains=params.cyclic_chains or [],
                )

                logger.info("RosettaFold3 inference completed")

            except Exception as e:
                logger.error("RosettaFold3 inference failed: %s", e, exc_info=True)
                raise ServerError(
                    "RosettaFold3 inference failed; see server logs for details."
                ) from e

            # Process outputs
            results = []

            # RF3 creates a subdirectory for each input
            item_output_dir = output_dir / item.name

            # Debug: Check what files exist
            logger.debug("Looking for outputs in: %s", item_output_dir)
            if item_output_dir.exists():
                all_files = list(item_output_dir.iterdir())
                logger.debug("Found %s files in output directory", len(all_files))
                for f in sorted(all_files)[:10]:  # Show first 10
                    logger.debug("- %s", f.name)

            # Find all generated CIF files in output directory
            # RF3 can create files with pattern {name}_model.cif or {name}_model_{idx}.cif.gz
            cif_files = sorted(item_output_dir.glob(f"{item.name}_model*.cif.gz"))

            # Also check for non-gzipped CIF files
            if not cif_files:
                cif_files = sorted(item_output_dir.glob(f"{item.name}_model*.cif"))

            if not cif_files:
                # Check if early stopped
                score_file = item_output_dir / f"{item.name}.score"
                if score_file.exists():
                    logger.warning("Prediction was early-stopped due to low confidence")
                    # Return empty result with early_stopped flag
                    result = RF3PredictResponseResult(
                        structure_cif="",
                        confidence=RF3ConfidenceScores(),
                        early_stopped=True,
                        sample_idx=0,
                    )
                    results.append(result)
                else:
                    raise ServerError(
                        "RosettaFold3 produced no structures or score file; "
                        "see server logs for details."
                    )
            else:
                logger.info("Found %s generated structures", len(cif_files))

                # Read confidence JSON if available
                confidence_json_path = (
                    item_output_dir / f"{item.name}_summary_confidences.json"
                )
                summary_confidences = {}
                if confidence_json_path.exists():
                    with open(confidence_json_path) as f:
                        summary_confidences = json.load(f)

                for idx, cif_path in enumerate(
                    cif_files[: params.diffusion_batch_size]
                ):
                    # Read CIF file
                    if cif_path.suffix == ".gz":
                        with gzip.open(cif_path, "rt") as f:
                            cif_content = f.read()
                    else:
                        with open(cif_path) as f:
                            cif_content = f.read()

                    # Try to read corresponding sample confidence JSON
                    # RF3 may output per-sample confidence files
                    sample_confidence_path = (
                        item_output_dir
                        / f"{item.name}_seed-{params.seed}_sample-{idx}_summary_confidences.json"
                    )
                    if sample_confidence_path.exists():
                        with open(sample_confidence_path) as f:
                            sample_conf = json.load(f)
                    else:
                        sample_conf = summary_confidences

                    # Read PAE if requested and available
                    pae = None
                    if params.include_pae:
                        pae_path = item_output_dir / f"{item.name}_pae_model_{idx}.npz"
                        if pae_path.exists():
                            pae_data = np.load(pae_path)
                            if "pae" in pae_data:
                                pae = pae_data["pae"].tolist()

                    # Read pLDDT if requested and available
                    plddt = None
                    if params.include_plddt:
                        plddt_path = (
                            item_output_dir / f"{item.name}_plddt_model_{idx}.npz"
                        )
                        if plddt_path.exists():
                            plddt_data = np.load(plddt_path)
                            if "plddt" in plddt_data:
                                plddt = plddt_data["plddt"].tolist()

                    # Create confidence scores
                    confidence = RF3ConfidenceScores(
                        ptm=sample_conf.get("ptm"),
                        iptm=sample_conf.get("iptm"),
                        ranking_score=sample_conf.get("ranking_score"),
                        has_clash=sample_conf.get("has_clash", False),
                        plddt=plddt,
                        pae=pae,
                    )

                    result = RF3PredictResponseResult(
                        structure_cif=cif_content,
                        confidence=confidence,
                        early_stopped=False,
                        sample_idx=idx,
                    )
                    results.append(result)

            logger.info("Processed %s prediction results", len(results))

        return RF3PredictResponse(results=[results])

    def _create_input_specification(  # noqa: C901
        self, item, params, temp_dir_path: Path
    ):
        """Convert API input to RF3 input specification JSON format.

        Args:
            item: RF3PredictRequestInput item
            params: RF3PredictParams
            temp_dir_path: Path to temporary directory for writing MSA files
        """
        spec = {
            "name": item.name,
            "components": [],
        }

        # Convert components
        for comp in item.components:
            comp_spec: dict = {}

            if comp.type:
                comp_spec["entity_type"] = comp.type.value

            if comp.sequence:
                comp_spec["seq"] = comp.sequence
            if comp.smiles:
                comp_spec["smiles"] = comp.smiles
            if comp.ccd_code:
                comp_spec["ccd_code"] = comp.ccd_code
            if comp.structure_cif:
                # Write inline CIF content to a temp file so foundry can read it
                temp_cif_path = temp_dir_path / f"{comp.name}_template.cif"
                temp_cif_path.write_text(comp.structure_cif)
                comp_spec["path"] = str(temp_cif_path)
            elif comp.structure_path:
                # Container-local path; only usable in test/internal scenarios
                comp_spec["path"] = comp.structure_path
            if comp.chain_id:
                comp_spec["chain_id"] = comp.chain_id
            # Handle MSA - same pattern as boltz
            if comp.msa_path:
                comp_spec["msa_path"] = comp.msa_path
            elif comp.alignment is not None and isinstance(comp.alignment, dict):
                # Handle alignment dictionary - same as boltz
                # Combine multiple A3M strings into one file
                from models.commons.data.a3m import combine_a3ms

                if len(comp.alignment) > 1:
                    logger.debug(
                        "[RF3] Merging %s A3Ms for component %s: %s",
                        len(comp.alignment),
                        comp.name,
                        list(comp.alignment.keys()),
                    )
                else:
                    logger.debug(
                        "[RF3] Using single A3M for component %s: %s",
                        comp.name,
                        list(comp.alignment.keys()),
                    )

                # Combine all A3M strings in the dict into one temporary file
                temp_msa_path = temp_dir_path / f"{comp.name}_msa.a3m"
                combine_a3ms(list(comp.alignment.values()), str(temp_msa_path))
                comp_spec["msa_path"] = str(temp_msa_path)
            elif comp.msa_content:
                # Write MSA content to temp file
                temp_msa_path = temp_dir_path / f"{comp.name}_msa.a3m"
                with open(temp_msa_path, "w") as f:
                    f.write(comp.msa_content)
                comp_spec["msa_path"] = str(temp_msa_path)

            spec["components"].append(comp_spec)

        # Add bonds if specified
        if item.bonds:
            spec["bonds"] = item.bonds

        return [spec]  # RF3 expects a list of specifications


if __name__ == "__main__":
    """
    Usage:
        python models/rf3/app.py

        # Force deploy to "biolm-models-dev" (staging) or "biolm-models" (prod):
        python models/rf3/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        RF3Model,
        description=f"Run and optionally deploy the {RF3Params.display_name} Modal app.",
    )
