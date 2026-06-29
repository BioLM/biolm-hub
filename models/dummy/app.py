import json
import os

import modal

from models.commons.core.decorator import modal_endpoint
from models.commons.core.logging import get_logger
from models.commons.modal.source import setup_source_layer
from models.commons.model.base import ModelMixinSnap
from models.commons.model.config import biolm_model_class
from models.commons.util.config import (
    cloudflare_r2_secret,
    common_requirements,
)
from models.dummy.config import MODEL_FAMILY
from models.dummy.schema import (
    DummyParams,
    DummySvcRequest,
    DummySvcResponse,
    DummySvcResponseResult,
)

logger = get_logger(__name__)

DEFAULT_DATA = {"hello": "world"}


def initialize_data():
    data_file_path = "/dummy_test_data.json"
    if not os.path.exists(data_file_path):
        with open(data_file_path, "w") as f:
            json.dump(DEFAULT_DATA, f)
        logger.info("Created test data at %s", data_file_path)


# Build Modal container image
image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
)
# Add all model files
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)
# Run initialization after model files are available
image = image.run_function(initialize_data)


# Define the app using unified config
app_name, modal_resource_spec = MODEL_FAMILY.get_app_config()
logger.info("App name: %s", app_name)
app = modal.App(app_name, image=image)


# Define the Dummy Model class
@app.cls(
    image=image,
    secrets=[cloudflare_r2_secret],
    enable_memory_snapshot=True,
    experimental_options={"enable_gpu_snapshot": True},
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class DummyModel(ModelMixinSnap):
    app_username: str = modal.parameter(default="default_user")
    # Define path to the data file in the container's root directory
    data_file_path = "/dummy_test_data.json"

    @modal.enter(snap=True)
    def setup_model(self):
        """
        Load the data from the data file into memory for GPU memory snapshot.
        """
        logger.info(
            "Loading %s model directly for GPU memory snapshot...",
            DummyParams.display_name,
        )

        if os.path.exists(self.data_file_path):
            with open(self.data_file_path) as f:
                self.data_file_content = json.load(f)
            logger.info("Loaded data from %s", self.data_file_path)
        else:
            self.data_file_content = DEFAULT_DATA
            logger.warning("No data file found; using default content.")

        logger.info(
            "%s model ready for prediction from GPU memory snapshot!",
            DummyParams.display_name,
        )

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def predict(self, payload: DummySvcRequest) -> DummySvcResponse:
        """
        Perform prediction using the dummy model.

        Parameters:
            payload (DummySvcRequest): The request payload containing input data.

        Returns:
            DummySvcResponse: The response with processed data.
        """
        results = []
        for item in payload.items:
            # Process the input field and fetch content from the loaded data
            response_field = item.dummy_model_input_field + "_processed_by_dummy_model"
            data_content = self.data_file_content.get("hello", "No data")
            results.append(
                DummySvcResponseResult(
                    dummy_svc_resp_field=response_field, data_file_content=data_content
                )
            )
        return DummySvcResponse(results=results)


if __name__ == "__main__":
    """
    Usage:
        python models/dummy/app.py
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        DummyModel,
        description=f"Run and optionally deploy the {DummyParams.display_name} Modal app.",
    )
