import modal
import numpy as np

from models.commons.core.decorator import modal_endpoint
from models.commons.core.logging import get_logger
from models.commons.modal.source import setup_source_layer
from models.commons.model.base import ModelMixin
from models.commons.model.config import biolm_model_class
from models.commons.util.config import (
    common_requirements,
    runtime_secrets,
)
from models.prody.config import MODEL_FAMILY
from models.prody.schema import (
    ProDyEncodeRequest,
    ProDyEncodeResponse,
    ProDyParams,
    ProDyPredictRequest,
    ProDyPredictResponse,
)
from models.prody.utils import compute_rmsd, process_structure_for_insty

logger = get_logger(__name__)

# Define the Docker image with necessary dependencies
image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install(
        "libopenblas-dev",
        "git",
        "wget",
        "gcc",
        "g++",
        "libffi-dev",
        "procps",
        "openbabel",
    )
    .uv_pip_install(common_requirements)
    .uv_pip_install(
        "prody==2.6.1",
        "numpy==1.26.4",
        "pandas==2.2.3",
        "openbabel-wheel==3.1.1.22",  # Python bindings for OpenBabel
        # commons.storage.acquisition imports `requests` at cold start; this
        # minimal algorithmic image has no transformers/hf dep to pull it in
        # transitively, so it must be installed explicitly.
        "requests==2.32.3",
    )
    # PDBFixer powers the default InSty hydrogen-addition path. It needs a
    # matching OpenMM (its hard runtime dep, which it does not pull in itself);
    # without OpenMM ProDy's addMissingAtoms raises
    # "Install PDBFixer and OpenMM in order to fix the protein structure".
    # pdbfixer 1.12.0 (PyPI) requires openmm>=8.2, so they are pinned together.
    .uv_pip_install(
        "openmm==8.2.0",
        "pdbfixer==1.12.0",
    )
)

# Add model source files
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)

# Get app configuration from MODEL_FAMILY
app_name, modal_resource_spec = MODEL_FAMILY.get_app_config()

# Define the Modal app
app = modal.App(app_name, image=image)


@app.cls(
    image=image,
    secrets=runtime_secrets(),
    enable_memory_snapshot=False,  # Disabled: snapshots cached stale code
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class ProDyModel(ModelMixin):
    app_username: str = modal.parameter(default="default_user")

    @modal.enter()
    def load_model(self) -> None:
        """Load ProDy and set seeds for determinism."""
        import random

        import prody  # noqa: F401  # Pre-import for faster first request

        seed = 42
        random.seed(seed)
        np.random.seed(seed)

        logger.info("ProDy model loaded successfully")

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def encode(self, payload: ProDyEncodeRequest) -> ProDyEncodeResponse:
        """Compute interactions and bonds using ProDy InSty."""
        num_items = len(payload.items)

        if num_items == 0:
            return ProDyEncodeResponse(results=[])

        # Process items sequentially (ProDy C extensions are not thread-safe)
        logger.info(f"Processing {num_items} items sequentially")

        results = []
        for item in payload.items:
            result_obj = process_structure_for_insty(item, payload.params)
            results.append(result_obj)

        return ProDyEncodeResponse(results=results)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def predict(self, payload: ProDyPredictRequest) -> ProDyPredictResponse:
        """Compute RMSD between two structures using ProDy."""
        results = []

        for item in payload.items:
            result = compute_rmsd(item, payload.params)
            results.append(result)

        return ProDyPredictResponse(results=results)


if __name__ == "__main__":
    """
    Usage:
        python models/prody/app.py

        # Force deploy to "biolm-hub-dev" or "biolm-hub" environment:
        python models/prody/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        ProDyModel,
        description=f"Run and optionally deploy the {ProDyParams.display_name} Modal app.",
    )
