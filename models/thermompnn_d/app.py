import os
import shutil
import tempfile

import modal
from pydantic import ValidationError

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
from models.thermompnn_d.config import (
    MODEL_FAMILY,
    thermompnn_d_commit_hash,
)
from models.thermompnn_d.download import get_model_dir
from models.thermompnn_d.schema import (
    ThermoMPNNDMode,
    ThermoMPNNDParams,
    ThermoMPNNDPredictParams,
    ThermoMPNNDPredictRequest,
    ThermoMPNNDPredictResponse,
    ThermoMPNNDPredictResponseItem,
)

logger = get_logger(__name__)

# No variant config needed - single model
variant_config = {}

# Build Modal container image
image = modal.Image.micromamba(python_version="3.10")
# Setup download layer with model weights
image = setup_download_layer(
    image,
    base_model_slug=ThermoMPNNDParams.base_model_slug,
    params_version=ThermoMPNNDParams.params_version,
    variant_config=variant_config,
)
# Add dependencies and packages
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .apt_install(["git", "wget", "gcc", "g++", "libffi-dev"])
    .uv_pip_install(
        [
            "biopython==1.79",
            "filelock==3.13.1",
            "fsspec==2024.3.1",
            "Jinja2==3.1.3",
            "MarkupSafe==2.1.5",
            "mpmath==1.3.0",
            "networkx==3.2.1",
            "numpy==1.23.5",
            "omegaconf==2.3.0",
            "pandas==2.0.3",
            "tqdm==4.66.1",
            "scipy==1.12.0",
            "scikit-learn==1.3.2",
        ]
    )
    .uv_pip_install(
        [
            "nvidia-cublas-cu12==12.1.3.1",
            "nvidia-cuda-cupti-cu12==12.1.105",
            "nvidia-cuda-nvrtc-cu12==12.1.105",
            "nvidia-cuda-runtime-cu12==12.1.105",
            "nvidia-cudnn-cu12==8.9.2.26",
            "nvidia-cufft-cu12==11.0.2.54",
            "nvidia-curand-cu12==10.3.2.106",
            "nvidia-cusolver-cu12==11.4.5.107",
            "nvidia-cusparse-cu12==12.1.0.106",
            "nvidia-nccl-cu12==2.19.3",
            "nvidia-nvjitlink-cu12==12.4.99",
            "nvidia-nvtx-cu12==12.1.105",
        ]
    )
    .uv_pip_install(
        [
            "ProDy==2.4.1",
            "pyparsing==3.1.1",
            "sympy==1.12",
            "torch==2.2.1",
            "triton==2.2.0",
            "typing_extensions==4.10.0",
            "pytorch-lightning==2.0.9",
            "torchmetrics==1.0.3",
            "wandb==0.15.12",
        ]
    )
    .workdir("/root")
    .run_commands(
        f"git clone https://github.com/Kuhlman-Lab/ThermoMPNN-D.git && cd ThermoMPNN-D && git checkout {thermompnn_d_commit_hash}",
    )
    .workdir("./ThermoMPNN-D")
    .run_commands("mkdir -p /tmp_pdbs", "mkdir -p /tmp_out")
)
# Finally, add all model files
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)


# Define the app using unified config
app_name, modal_resource_spec = MODEL_FAMILY.get_app_config(**variant_config)
logger.info("App name: %s", app_name)
app = modal.App(app_name, image=image)


@app.cls(
    image=image,
    secrets=[cloudflare_r2_secret],
    enable_memory_snapshot=True,
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class ThermoMPNNDModel(ModelMixinSnap):
    app_username: str = modal.parameter(default="default_user")

    @modal.enter(snap=True)
    def load_model(self):
        """
        Loads the ThermoMPNN-D models on CPU for memory snapshot.
        Note: We load both single and epistatic models for flexibility.
        """
        import torch

        from models.thermompnn_d.util import load_thermompnn_d

        logger.info("Loading ThermoMPNN-D models on CPU for memory snapshot...")

        # Set deterministic behavior for consistent results across CPU loading
        torch.manual_seed(42)

        self.torch = torch
        self.model_dir = get_model_dir()

        logger.info(
            "Loading ThermoMPNN-D models on CPU for memory snapshot from: %s",
            self.model_dir,
        )

        # Load both single and epistatic models (additive uses single model)
        # Models are loaded in eval mode by load_thermompnn_d
        self.model_single, self.config_single = load_thermompnn_d(
            model_dir=self.model_dir,
            mode="single",
            device=torch.device("cpu"),  # Force CPU loading for snapshot
        )
        self.model_single.eval()  # Ensure eval mode for snapshot

        self.model_epistatic, self.config_epistatic = load_thermompnn_d(
            model_dir=self.model_dir,
            mode="epistatic",
            device=torch.device("cpu"),  # Force CPU loading for snapshot
        )
        self.model_epistatic.eval()  # Ensure eval mode for snapshot

        logger.info("Completed CPU load of ThermoMPNN-D models for memory snapshot")

    @modal.enter(snap=False)
    def setup_model(self):
        """
        Transfers models to GPU and starts billing.
        """
        # Set deterministic behavior for consistent results across GPU loading
        if self.torch.cuda.is_available():
            self.torch.cuda.manual_seed_all(42)

        # Get device and transfer models to GPU
        self.device = get_torch_device()

        logger.info("Transferring ThermoMPNN-D models to device=%s...", self.device)

        self.model_single = self.model_single.to(self.device)
        self.model_epistatic = self.model_epistatic.to(self.device)

        logger.info("ThermoMPNN-D models ready for inference")

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def predict(self, payload: ThermoMPNNDPredictRequest) -> ThermoMPNNDPredictResponse:
        """
        Predict thermostability changes (ddG) for single or double mutations.

        Supports three modes:
        - single: Single point mutations, predicts ddG for each
        - additive: Double mutations with additive model
        - epistatic: Double mutations with epistatic interaction model

        If mutations is None, performs site-saturation mutagenesis (SSM) scan.
        For double mutation modes, uses distance threshold to filter pairs.

        Returns predictions with mutation string, positions, wildtype/mutant
        amino acids, predicted ddG, and CA-CA distance for double mutations.
        """
        from models.thermompnn_d.util import predict  # type: ignore

        try:
            # Validate params
            params = ThermoMPNNDPredictParams.model_validate(
                payload.params.model_dump(exclude_unset=True, exclude_none=True)
            )
        except ValidationError as e:
            raise UserError(f"Invalid parameters: {e}") from e

        # Get PDB and mutations from request
        item = payload.items[0]
        pdb_string = item.pdb
        mutations = item.mutations

        # Write PDB to unique temporary directory (avoids race conditions)
        temp_dir = tempfile.mkdtemp(prefix="thermompnn_d_")
        pdb_path = os.path.join(temp_dir, "input.pdb")
        try:
            with open(pdb_path, "w") as f:
                f.write(pdb_string)
        except OSError as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise UserError(f"Failed to write PDB file: {e}") from e

        try:
            # Select model and config based on mode (use enum comparison)
            if params.mode in (ThermoMPNNDMode.SINGLE, ThermoMPNNDMode.ADDITIVE):
                model = self.model_single
                config = self.config_single
            else:  # ThermoMPNNDMode.EPISTATIC
                model = self.model_epistatic
                config = self.config_epistatic

            # Run prediction
            results = predict(
                model=model,
                config=config,
                pdb_path=pdb_path,
                mutations=mutations,
                mode=params.mode.value,
                chain=params.chain,
                distance=params.distance,
                threshold=params.threshold,
                batch_size=2048,  # Default batch size for epistatic
            )

            # Format response
            response_items = [
                ThermoMPNNDPredictResponseItem.model_validate(result)
                for result in results
            ]

            return ThermoMPNNDPredictResponse(results=response_items)
        finally:
            # Clean up temporary files
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)


if __name__ == "__main__":
    """
    Usage:
        python models/thermompnn_d/app.py

        # Force deploy to "qa" or "main" environment:
        python models/thermompnn_d/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        ThermoMPNNDModel,
        description=f"Run and optionally deploy the {ThermoMPNNDParams.display_name} Modal app.",
    )
