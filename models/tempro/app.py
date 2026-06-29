import os
from typing import TYPE_CHECKING

import modal

if TYPE_CHECKING:
    import numpy as np

from models.commons.core.decorator import modal_endpoint
from models.commons.core.error import ModelExecutionError
from models.commons.core.logging import get_logger
from models.commons.modal.downloader import setup_download_layer
from models.commons.modal.source import setup_source_layer
from models.commons.model.base import ModelMixinSnap
from models.commons.model.config import biolm_model_class
from models.commons.util.config import (
    cloudflare_r2_secret,
    common_requirements,
)
from models.commons.util.environment import parse_variant
from models.esm2.schema import (
    ESM2EncodeIncludeOptions,
    ESM2EncodeRequest,
    ESM2EncodeRequestItem,
    ESM2EncodeRequestParams,
)
from models.tempro.config import MODEL_FAMILY, TEMPRO_ESM_LAYER_MAPPING
from models.tempro.download import get_model_dir
from models.tempro.schema import (
    TemproESM2Sizes,
    TemproParams,
    TemproPredictRequest,
    TemproPredictResponse,
    TemproPredictResponseResult,
)

logger = get_logger(__name__)

variant_config = parse_variant(
    env_var_name="ESM2_SIZE",
    allowed_values=TemproESM2Sizes,
    default=TemproESM2Sizes.SIZE_650M,
)
esm2_size = variant_config["ESM2_SIZE"]


# Build Modal container image
image = modal.Image.debian_slim(python_version="3.10")
# Setup download layer with model weights
image = setup_download_layer(
    image,
    base_model_slug=TemproParams.base_model_slug,
    weights_version=TemproParams.weights_version,
    variant_config=variant_config,
)
# Add dependencies and packages
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .uv_pip_install(
        # Versions below are from TEMPRO repo
        "tensorflow-cpu==2.10.1",  # Use CPU-only TensorFlow for smaller image
        "keras==2.10.0",
        "numpy==1.23.5",
    )
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
    enable_memory_snapshot=True,  # Enable Modal memory snapshots for faster cold starts
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class TemproModel(ModelMixinSnap):
    app_username: str = modal.parameter(default="default_user")
    esm2_size: str = esm2_size

    @modal.enter(snap=True)
    def load_model(self):
        """Load the pre-trained Keras model on CPU for memory snapshot."""

        import keras
        import tensorflow as tf

        # Silence TensorFlow warnings about missing GPU libraries (TEMPRO runs on CPU)
        os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"  # 0=all, 1=info, 2=warning, 3=error
        tf.get_logger().setLevel("ERROR")

        logger.info("Loading TEMPRO %s model for snapshot...", self.esm2_size)

        # Set deterministic behavior for consistent results
        tf.random.set_seed(42)

        # Get model directory and load Keras model
        model_dir = get_model_dir(self.esm2_size)
        model_path = model_dir / "saved_models" / f"ESM_{self.esm2_size.upper()}.keras"

        logger.info("Loading Keras model from: %s", model_path)
        self.keras_model = keras.models.load_model(model_path)

        # ESM2 configuration - layer to extract embeddings from
        self.esm_layer = TEMPRO_ESM_LAYER_MAPPING[TemproESM2Sizes(self.esm2_size)]

        logger.info("TEMPRO %s model loaded into memory snapshot", self.esm2_size)

    @modal.enter(snap=False)
    def setup_model(self):
        """Post-snapshot setup: initialize cross-model ESM2 reference."""
        esm_app_name = f"esm2-{self.esm2_size}"
        try:
            ESM2Model = modal.Cls.from_name(esm_app_name, "ESM2Model")
            self.esm2_model_instance = ESM2Model(app_username=self.app_username)
        except Exception as e:
            raise RuntimeError(f"Cannot reach ESM2 model '{esm_app_name}': {e}") from e
        logger.info("TEMPRO %s ready (ESM2 layer %s)", self.esm2_size, self.esm_layer)

    def get_esm2_embeddings(self, sequences: list[str]) -> "np.ndarray":
        """
        Call ESM2 via Modal function lookup to get embeddings.

        Args:
            sequences: List of protein sequences to encode

        Returns:
            numpy array of mean-pooled embeddings, shape (batch_size, embedding_dim)
        """
        logger.info("Calling ESM2 for %s sequences...", len(sequences))

        # Prepare request for ESM2
        request_payload = ESM2EncodeRequest(
            params=ESM2EncodeRequestParams(
                repr_layers=[self.esm_layer], include=[ESM2EncodeIncludeOptions.MEAN]
            ),
            items=[ESM2EncodeRequestItem(sequence=seq) for seq in sequences],
        )

        try:
            # Call ESM2 remotely using the pre-initialized instance from setup_model
            with modal.enable_output():
                response = self.esm2_model_instance.encode.remote(request_payload)

            # response is a dict (serialized by the modal_endpoint decorator)
            results = response["results"]
            logger.info("ESM2 call successful, got %s results", len(results))

            # Extract embeddings - results is a list of dicts
            embeddings = []
            for i, result in enumerate(results):
                # result is a dict, embeddings is a list of dicts
                embeddings_data = result["embeddings"]
                if not embeddings_data:
                    raise ModelExecutionError(
                        f"No embeddings returned for sequence index {i}"
                    )

                # Get the first (and only) layer's embedding
                layer_embedding = embeddings_data[0]
                embeddings.append(layer_embedding["embedding"])

            import numpy as np

            return np.array(embeddings, dtype=np.float32)

        except ModelExecutionError:
            raise
        except Exception as e:
            logger.error("Error calling ESM2: %s", e, exc_info=True)
            raise RuntimeError(f"Failed to get ESM2 embeddings: {e}") from e

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def predict(self, payload: TemproPredictRequest) -> TemproPredictResponse:
        """
        Predict melting temperatures for nanobody sequences.
        """
        sequences = [item.sequence for item in payload.items]

        logger.info(
            "Predicting Tm for %s sequences using TEMPRO %s",
            len(sequences),
            self.esm2_size,
        )

        import numpy as np

        # Step 1: Get ESM2 embeddings
        embeddings = self.get_esm2_embeddings(sequences)
        logger.debug("Got embeddings shape: %s", embeddings.shape)

        # Step 2: Predict using Keras model
        logger.info("Running Keras model prediction...")
        predictions = self.keras_model.predict(embeddings, verbose=0)

        # Step 3: Build response
        results = []
        for i, (_sequence, tm_pred) in enumerate(
            zip(sequences, predictions, strict=False)
        ):
            # Extract scalar prediction (predictions come as [[value]] from Keras)
            tm_value = (
                float(tm_pred[0])
                if isinstance(tm_pred, list | np.ndarray)
                else float(tm_pred)
            )

            result = TemproPredictResponseResult(tm=tm_value)
            results.append(result)

            logger.debug("Sequence %s: Tm = %.2f C", i + 1, tm_value)

        logger.info("TEMPRO prediction complete for %s sequences", len(results))
        return TemproPredictResponse(results=results)


if __name__ == "__main__":
    """
    Usage:
        ESM2_SIZE="650m" python models/tempro/app.py
        ESM2_SIZE="3b" python models/tempro/app.py

        # Force deploy to biolm-models-dev or biolm-models:
        ESM2_SIZE="650m" python models/tempro/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        TemproModel,
        description=f"Run and optionally deploy the {TemproParams.display_name} {esm2_size} Modal app.",
    )
