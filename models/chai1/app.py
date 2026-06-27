from pathlib import Path

import modal

from models.chai1.config import MODEL_FAMILY, Chai1ResourceSpec
from models.chai1.download import get_model_dir
from models.chai1.schema import (
    Chai1Params,
    Chai1PredictRequest,
    Chai1PredictResponse,
    Chai1PredictResponseResult,
    Chai1ScoreOptions,
)
from models.commons.core.decorator import modal_endpoint
from models.commons.core.error import UserError
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

logger = get_logger(__name__)

# Build Modal container image
image = (
    modal.Image.from_registry("pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime")
    .apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    # NOTE: Pre-install all dependencies if download layer might depend upon it
    .apt_install("git", "build-essential")
    .pip_install(
        "biopython==1.83",
        "chai-lab==0.6.1",
        "pandas==2.1.1",  # For data handling
        "pyarrow==13.0.0",  # For Parquet handling
        gpu=Chai1ResourceSpec.gpu,  # Use GPU from config
    )
    .env(
        {
            "DISABLE_PANDERA_IMPORT_WARNING": "True",
        }
    )
)
# Setup download layer with model weights
image = setup_download_layer(
    image,
    base_model_slug=Chai1Params.base_model_slug,
    params_version=Chai1Params.params_version,
    variant_config=None,  # this model has no variants
)
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
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class Chai1Model(ModelMixinSnap):
    app_username: str = modal.parameter(default="default_user")

    @modal.enter(snap=True)
    def load_model(self):
        """
        Loads Chai1 environment and configuration on CPU for memory snapshot.
        Note: GPUs are not available during snap=True phase, so we only set up
        the environment. The model will be loaded on first inference call.
        """
        import os

        import torch

        logger.info("Loading Chai1 environment on CPU for memory snapshot...")

        # Set deterministic behavior for consistent results
        torch.manual_seed(42)
        # Note: CUDA not available during snap=True, so skip cuda.manual_seed_all

        self.torch = torch
        self.model_dir = get_model_dir()

        logger.info("Chai1 model directory: %s", self.model_dir)

        # Verify the CHAI_DOWNLOADS_DIR is already set (from download phase)
        chai_dir = os.environ.get("CHAI_DOWNLOADS_DIR")
        if chai_dir:
            logger.info("CHAI_DOWNLOADS_DIR already set to: %s", chai_dir)
        else:
            # Set it if not already set
            os.environ["CHAI_DOWNLOADS_DIR"] = str(self.model_dir)
            logger.info("Set CHAI_DOWNLOADS_DIR to: %s", self.model_dir)

        # Verify key files exist
        from pathlib import Path

        models_v2_dir = Path(self.model_dir) / "models_v2"
        if models_v2_dir.exists():
            pt_files = list(models_v2_dir.glob("*.pt"))
            lock_files = list(models_v2_dir.glob("*.download_lock"))
            logger.info(
                "models_v2 directory found with %s .pt files and %s lock files",
                len(pt_files),
                len(lock_files),
            )
        else:
            logger.warning(
                "Warning: models_v2 directory not found at %s", models_v2_dir
            )
            logger.warning("Chai1 may attempt to download weights")

        conformers_file = Path(self.model_dir) / "conformers_v1.apkl"
        if conformers_file.exists():
            logger.info(
                f"conformers_v1.apkl found ({conformers_file.stat().st_size / 1024**2:.1f} MB)"
            )
        else:
            logger.warning("Warning: conformers_v1.apkl not found")

        # Import chai-lab components (imports are fine during snap=True)
        from chai_lab.chai1 import run_inference
        from chai_lab.data.parsing.msas.aligned_pqt import merge_a3m_in_directory

        self.run_inference = run_inference
        self.merge_a3m_in_directory = merge_a3m_in_directory

        logger.info("Chai1 environment prepared for memory snapshot")

        # Diagnostic: Check if chai1 created any bypass directories
        bypass_locations = [
            Path.home() / ".cache" / "chai_lab",
            Path.home() / ".chai_lab",
            Path("/tmp") / "chai_downloads",
        ]
        for location in bypass_locations:
            if location.exists():
                logger.warning(
                    "Found chai1 directory at %s - may indicate bypass", location
                )

    @modal.enter(snap=False)
    def setup_model(self):
        """Set up GPU device after snapshot restore."""
        logger.info("Setting up Chai1 on GPU after snapshot restore...")

        if self.torch.cuda.is_available():
            self.torch.cuda.manual_seed_all(42)

        # Get device for GPU inference
        self.device = get_torch_device()

        logger.info("Chai1 ready for inference on %s", self.device)
        logger.info("Model will be loaded on first inference call")

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def fold(  # noqa: C901
        # FIXME(noqa: C901): Refactor to reduce complexity below the linter's threshold.
        self,
        payload: Chai1PredictRequest,
    ) -> Chai1PredictResponse:
        """
        Performs prediction using the Chai-1 model.
        """
        import tempfile

        params = payload.params
        item = payload.items[0]  # Batch size fixed to 1

        # Convert entities to FASTA format
        fasta_lines = []
        for molecule in item.molecules:
            if not molecule.sequence and not molecule.smiles:
                continue
            if molecule.sequence:
                fasta_lines.append(f">{molecule.type}|name={molecule.name}")
                fasta_lines.append(molecule.sequence)
            elif molecule.smiles:
                fasta_lines.append(f">{molecule.type}|name={molecule.name}")
                fasta_lines.append(molecule.smiles)

        if not fasta_lines:
            raise UserError("No valid sequences or SMILES found in molecules.")

        # Join lines with newlines and add final newline
        fasta_content = "\n".join(fasta_lines) + "\n"
        logger.info("Converted molecules to FASTA format.")

        # Use a temporary file to pass the FASTA data
        with tempfile.NamedTemporaryFile(delete=True, suffix=".fasta") as temp_fasta:
            temp_fasta.write(fasta_content.encode("utf-8"))
            temp_fasta.flush()  # Ensure the file is written to disk

            logger.info("Temporary FASTA file created at: %s", temp_fasta.name)

            # Use a temporary directory for the output
            with tempfile.TemporaryDirectory() as temp_output_dir:
                output_dir = Path(temp_output_dir)
                logger.info("Temporary output directory created at: %s", output_dir)

                # Create a temporary directory for MSAs
                with tempfile.TemporaryDirectory() as temp_msa_dir:
                    msa_dir = Path(temp_msa_dir)
                    logger.info("Temporary MSA directory created at: %s", msa_dir)

                    # Process alignments for protein molecules
                    for molecule in item.molecules:
                        if (
                            molecule.type == "protein"
                            and molecule.alignment is not None
                        ):
                            # Create a subdirectory for this molecule's MSAs
                            molecule_msa_dir = msa_dir / molecule.name
                            molecule_msa_dir.mkdir(exist_ok=True)

                            # Write each a3m file
                            for db, a3m_content in molecule.alignment.items():
                                if db == "small_bfd":
                                    filename = "hits_bfd_uniclust.a3m"  # TODO: check why just BFD is not allowed
                                else:
                                    filename = f"hits_{db.value}.a3m"

                                a3m_path = molecule_msa_dir / filename
                                with open(a3m_path, "w") as f:
                                    f.write(a3m_content)
                                logger.info(
                                    "Written %s for molecule %s",
                                    filename,
                                    molecule.name,
                                )

                            # Merge a3m files for this molecule
                            self.merge_a3m_in_directory(
                                str(molecule_msa_dir), output_directory=str(msa_dir)
                            )
                            logger.info(
                                "Merged a3m files for molecule %s", molecule.name
                            )

                    # Run inference using the temporary files and directory
                    candidates = self.run_inference(
                        fasta_file=Path(temp_fasta.name),
                        output_dir=output_dir,
                        msa_directory=msa_dir,
                        use_esm_embeddings=params.use_esm_embeddings,
                        num_trunk_recycles=params.num_trunk_recycles,
                        num_diffn_timesteps=params.num_diffusion_timesteps,
                        num_diffn_samples=params.num_diffn_samples,
                        seed=params.seed,
                        device=self.device,
                    )

                    logger.info("Run inference completed.")
                    logger.info(
                        "Number of CIF paths generated: %s", len(candidates.cif_paths)
                    )

                    if len(candidates.cif_paths) == 0:
                        raise UserError(
                            "No CIF structures generated. Please check your inputs or model parameters."
                        )

                    results = []
                    # Iterate over CIF files and process them
                    for idx, cif_path in enumerate(candidates.cif_paths):
                        cif_file_path = Path(cif_path)
                        if not cif_file_path.exists():
                            raise FileNotFoundError(
                                f"Missing CIF file: {cif_file_path}"
                            )

                        logger.info(
                            "Processing CIF file %s/%s: %s",
                            idx + 1,
                            len(candidates.cif_paths),
                            cif_file_path,
                        )

                        # Read the CIF content
                        with cif_file_path.open("r") as cif_file:
                            cif_content = cif_file.read()

                        # Create the response entry for this CIF file
                        result = Chai1PredictResponseResult(
                            cif=cif_content,
                            pae=(
                                candidates.pae[idx].tolist()
                                if Chai1ScoreOptions.PAE in params.include
                                else None
                            ),
                            plddt=(
                                candidates.plddt[idx].tolist()
                                if Chai1ScoreOptions.PLDDT in params.include
                                else None
                            ),
                        )
                        results.append(result)

                    logger.info("All CIF files processed successfully.")

        # Return the response with all CIF files and their metadata
        return Chai1PredictResponse(results=[results])


if __name__ == "__main__":
    """
    Usage:
        python models/chai1/app.py

        # Force deploy to "qa" or "main" environment:
        python models/chai1/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        Chai1Model,
        description=f"Run and optionally deploy the {Chai1Params.display_name} Modal app.",
    )
