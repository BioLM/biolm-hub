import os
import tempfile
from pathlib import Path
from typing import Any, Optional

import modal

from models.commons.core.decorator import modal_endpoint
from models.commons.core.error import (
    ServerError,
    UnsupportedOptionError,
    ValidationError400,
)
from models.commons.core.logging import get_logger
from models.commons.modal.downloader import setup_download_layer
from models.commons.modal.source import setup_source_layer
from models.commons.model.base import ModelMixinSnap
from models.commons.model.config import biolm_model_class
from models.commons.util.config import (
    common_requirements,
    runtime_secrets,
)
from models.commons.util.device import get_torch_device
from models.commons.util.environment import parse_variant
from models.immunebuilder.config import MODEL_FAMILY
from models.immunebuilder.download import get_model_dir
from models.immunebuilder.schema import (
    ImmuneBuilderModelTypes,
    ImmuneBuilderParams,
    ImmuneBuilderPredictParams,
    ImmuneBuilderPredictRequest,
    ImmuneBuilderPredictRequestItem,
    ImmuneBuilderPredictResponse,
    ImmuneBuilderPredictResponseResult,
)

logger = get_logger(__name__)

variant_config = parse_variant(
    env_var_name="MODEL_TYPE",
    allowed_values=ImmuneBuilderModelTypes,
    default=ImmuneBuilderModelTypes.TCRBUILDER2,
)
model_type = variant_config["MODEL_TYPE"]


def prebuild_immunebuilder_models() -> None:
    """
    Pre-download ImmuneBuilder models during the build phase to avoid download
    during memory snapshot creation.
    """
    import time

    from ImmuneBuilder import ABodyBuilder2, NanoBodyBuilder2, TCRBuilder2

    model_dir = get_model_dir(model_type)

    logger.info(
        "Pre-building ImmuneBuilder model '%s' during build phase...", model_type
    )
    logger.info("Model directory: %s", model_dir)
    logger.info("Loading ONLY %s model (not all variants!)", model_type)
    logger.info("Start time: %s", time.strftime("%H:%M:%S"))

    start_time = time.time()

    # Ensure the model directory exists
    model_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Initialize the specific model based on enum (no string fallback needed)
        logger.info("Initializing %s model...", model_type)

        if model_type == ImmuneBuilderModelTypes.NANOBODYBUILDER2:
            logger.info("Initializing NanoBodyBuilder2...")
            model = NanoBodyBuilder2(weights_dir=model_dir)
        elif model_type == ImmuneBuilderModelTypes.ABODYBUILDER2:
            logger.info("Initializing ABodyBuilder2...")
            model = ABodyBuilder2(weights_dir=model_dir)
        elif model_type == ImmuneBuilderModelTypes.TCRBUILDER2PLUS:
            logger.info("Initializing TCRBuilder2Plus...")
            model = TCRBuilder2(weights_dir=model_dir)
        elif model_type == ImmuneBuilderModelTypes.TCRBUILDER2:
            logger.info("Initializing TCRBuilder2...")
            model = TCRBuilder2(
                weights_dir=model_dir, use_TCRBuilder2_PLUS_weights=False
            )
        else:
            # This should not happen with proper enum validation
            raise UnsupportedOptionError(
                f"Unknown model type: {model_type}. "
                f"Available types: {list(ImmuneBuilderModelTypes)}"
            )

        end_time = time.time()
        duration = end_time - start_time
        logger.info(
            "Successfully pre-built ImmuneBuilder model '%s' in %.2fs",
            model_type,
            duration,
        )
        logger.info("End time: %s", time.strftime("%H:%M:%S"))

        # Check if weights were loaded from R2 or downloaded from library remote
        if model_dir.exists() and any(model_dir.iterdir()):
            logger.info("Model weights loaded from R2 cache!")
        else:
            logger.info("Model weights downloaded from ImmuneBuilder library remote")

        # Clean up the model object to free memory
        del model

    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        logger.warning("Error during model pre-build after %.2fs: %s", duration, e)
        logger.warning("Model will be downloaded during runtime instead")
        # Don't fail the build, just log the issue


# Build Modal container image
image = modal.Image.micromamba(python_version="3.12")
# Setup download layer with model weights
image = setup_download_layer(
    image,
    base_model_slug=ImmuneBuilderParams.base_model_slug,
    weights_version=ImmuneBuilderParams.weights_version,
    variant_config=variant_config,
)
# Add dependencies and packages
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .micromamba_install("openmm=8.4.0", "pdbfixer=1.10", channels=["conda-forge"])
    .apt_install("git", "wget")
    .micromamba_install("biopython", channels=["conda-forge"])
    .micromamba_install("hmmer=3.3.2", channels=["conda-forge", "bioconda"])
    # Install ANARCI for antibody numbering (PyPI package includes pre-built
    # germline data — avoids flaky IMGT server fetches during source build)
    .uv_pip_install("anarci==2026.2.13.2")
    .uv_pip_install("ImmuneBuilder==1.2")
    .apt_install("libopenblas-dev")
    .run_function(prebuild_immunebuilder_models)
)
# Finally, add all model files
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)


# Define the app using unified config
app_name, modal_resource_spec = MODEL_FAMILY.get_app_config(**variant_config)
logger.info("App name: %s", app_name)
app = modal.App(app_name, image=image)


@app.cls(
    image=image,
    secrets=runtime_secrets(),
    enable_memory_snapshot=True,
    experimental_options={"enable_gpu_snapshot": True},
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class ImmuneBuilderModel(ModelMixinSnap):
    model_type: str = model_type

    def _load_model_by_type(self, weights_dir: Optional[Path]) -> Any:
        """Load the appropriate model based on model_type.

        Args:
            weights_dir: Required path to model weights directory.
                         This ensures we always use R2 cached weights when available.

        Returns:
            An ImmuneBuilder model instance (ABodyBuilder2 / NanoBodyBuilder2 /
            TCRBuilder2); the ImmuneBuilder library ships no type stubs, so the
            precise class can't be named here.
        """
        import time

        from ImmuneBuilder import ABodyBuilder2, NanoBodyBuilder2, TCRBuilder2

        if weights_dir is None:
            raise ServerError("weights_dir is required for _load_model_by_type()")

        logger.info("Loading %s with weights_dir: %s", self.model_type, weights_dir)

        # Check if we're using R2 cache or library remote
        if weights_dir.exists() and any(weights_dir.iterdir()):
            logger.info("Using R2 cached weights from: %s", weights_dir)
            source = "R2 cache"
        else:
            logger.info("No R2 cache found, will download from library remote")
            source = "library remote"

        load_start = time.time()

        if self.model_type == ImmuneBuilderModelTypes.NANOBODYBUILDER2:
            model = NanoBodyBuilder2(weights_dir=weights_dir)
        elif self.model_type == ImmuneBuilderModelTypes.ABODYBUILDER2:
            model = ABodyBuilder2(weights_dir=weights_dir)
        elif self.model_type == ImmuneBuilderModelTypes.TCRBUILDER2PLUS:
            model = TCRBuilder2(weights_dir=weights_dir)
        elif self.model_type == ImmuneBuilderModelTypes.TCRBUILDER2:
            model = TCRBuilder2(
                weights_dir=weights_dir, use_TCRBuilder2_PLUS_weights=False
            )
        else:
            raise UnsupportedOptionError(
                f"Invalid ImmuneBuilder Model Type: {self.model_type}"
            )

        load_duration = time.time() - load_start
        logger.info("Model loaded from %s in %.2fs", source, load_duration)
        return model

    @modal.enter(snap=True)
    def setup_model(self) -> None:
        """Load model directly on GPU for GPU memory snapshot with deterministic behavior."""
        import time

        import torch

        logger.info(
            "Loading ImmuneBuilder model directly on GPU for GPU memory snapshot..."
        )
        logger.info("Load start time: %s", time.strftime("%H:%M:%S"))

        load_start_time = time.time()

        # Set deterministic behavior for consistent results
        torch.manual_seed(42)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(42)

        self.model_dir = get_model_dir(self.model_type)

        # Get device and setup for GPU inference
        self.device = get_torch_device()

        logger.info(
            "Loading ImmuneBuilder model '%s' directly on GPU from: %s",
            self.model_type,
            self.model_dir,
        )

        # Load model - ImmuneBuilder models handle device loading internally
        # and will download models automatically if they don't exist
        try:
            logger.info("Attempting to load model from: %s", self.model_dir)

            # Check if we have R2 cached weights
            if self.model_dir.exists() and any(self.model_dir.iterdir()):
                logger.info("Found R2 cached weights - loading from cache")
            else:
                logger.info(
                    "No R2 cache found - will download from ImmuneBuilder library"
                )

            model_load_start = time.time()
            self.model = self._load_model_by_type(self.model_dir)
            model_load_duration = time.time() - model_load_start

            logger.info("Model loading took %.2fs", model_load_duration)

        except Exception:
            logger.error("Failed to load model from %s", self.model_dir, exc_info=True)
            raise

        load_end_time = time.time()
        total_duration = load_end_time - load_start_time
        logger.info(
            "ImmuneBuilder model '%s' loaded directly on %s for GPU memory snapshot!",
            self.model_type,
            self.device,
        )
        logger.info("Total load time: %.2fs", total_duration)
        logger.info("Load end time: %s", time.strftime("%H:%M:%S"))

    def _pre_process_payload(
        self, payload: ImmuneBuilderPredictRequest
    ) -> list[ImmuneBuilderPredictRequestItem]:
        for item in payload.items:
            if item._kind == self.model_type:
                continue  # Valid case
            if (
                item._kind == ImmuneBuilderModelTypes.TCRBUILDER2
                and hasattr(item, "_kind2")
                and item._kind2 == ImmuneBuilderModelTypes.TCRBUILDER2PLUS
                and self.model_type == ImmuneBuilderModelTypes.TCRBUILDER2PLUS
            ):
                continue  # Exception case

            # Create error message that handles missing _kind2
            kind2_str = f" and '{item._kind2}'" if hasattr(item, "_kind2") else ""
            # Caller routed the wrong chain type to this variant -> 400, not 500.
            raise ValidationError400(
                f"Mismatch detected: expected '{self.model_type}' but got '{item._kind}'{kind2_str} in request"
            )

        return payload.items

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def fold(
        self, payload: ImmuneBuilderPredictRequest
    ) -> ImmuneBuilderPredictResponse:
        """
        Performs structure prediction using the ImmuneBuilder models.

        Parameters:
        - payload (ImmuneBuilderPredictRequest): The request object containing sequences and parameters.

        Returns:
        - ImmuneBuilderPredictResponse: The response containing pdb predictions results.
        """
        inputs = self._pre_process_payload(payload)

        # Set seed for reproducibility (params is optional; fall back to defaults).
        params = payload.params or ImmuneBuilderPredictParams()
        self.seed_everything(params.seed)

        results: list[ImmuneBuilderPredictResponseResult] = []
        try:
            for input in inputs:
                with tempfile.NamedTemporaryFile(
                    mode="w+", suffix=".pdb", delete=False
                ) as tmp_file:
                    output_file = tmp_file.name

                # ImmuneBuilder's library API expects single-letter chain keys
                # (H/L for antibody+nanobody, A/B for TCR). Map the canonical
                # field names back to those keys, dropping any unset chains.
                chain_inputs = {
                    "H": input.heavy_chain,
                    "L": input.light_chain,
                    "A": input.tcr_alpha,
                    "B": input.tcr_beta,
                }
                chain_inputs = {
                    key: seq for key, seq in chain_inputs.items() if seq is not None
                }
                try:
                    result_obj = self.model.predict(chain_inputs)
                    result_obj.save(output_file)
                    with open(output_file) as f:
                        pdb_str = f.read()
                        results.append(ImmuneBuilderPredictResponseResult(pdb=pdb_str))

                finally:
                    if os.path.exists(output_file):
                        os.remove(output_file)

        except ValidationError400:
            raise
        except Exception as e:
            # ANARCI numbering failures are a documented failure mode for unusual
            # sequences that pass extended-AA validation but fail immune-region
            # identification — these are caller-input mistakes, not server faults.
            err_str = str(e).lower()
            if any(
                kw in err_str
                for kw in ("anarci", "numbering", "no sequence", "not a valid")
            ):
                raise ValidationError400(
                    "Sequence failed ANARCI immune-region numbering. "
                    "Ensure the input is a valid antibody, nanobody, or TCR sequence."
                ) from e
            logger.error("Model call failed", exc_info=True)
            raise

        return ImmuneBuilderPredictResponse(results=results)

    def seed_everything(self, seed: int = 42, deterministic: bool = True) -> None:
        """Set seed for reproducibility across random, NumPy, and torch.

        Args:
            seed (int): Seed value.
            deterministic (bool): If True, sets flags for deterministic behavior.
        """
        from models.commons.util.device import seed_torch

        # Shared core: Python, NumPy, torch RNGs + cuDNN determinism.
        seed_torch(seed, deterministic)

        logger.info(
            "Seeding everything with seed %s. Deterministic: %s", seed, deterministic
        )


if __name__ == "__main__":
    """
    Usage:
        MODEL_TYPE="abodybuilder2" python models/immunebuilder/app.py

        # Deploy to your configured Modal environment:
        MODEL_TYPE="abodybuilder2" python models/immunebuilder/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        ImmuneBuilderModel,
        description=f"Run and optionally deploy the {ImmuneBuilderParams.display_name} {model_type} Modal app.",
    )
