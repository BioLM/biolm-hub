import os
from functools import lru_cache
from typing import TYPE_CHECKING

import modal

if TYPE_CHECKING:
    import numpy as np

from models.commons.billing.mixin import BillingMixinSnap
from models.commons.core.decorator import modal_endpoint
from models.commons.modal.downloader import setup_download_layer
from models.commons.modal.source import setup_source_layer
from models.commons.model.config import biolm_model_class
from models.commons.util.config import (
    cloudflare_r2_secret,
    common_requirements,
    redis_url_secret,
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
    params_version=TemproParams.params_version,
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
print(f"App name: {app_name}")
app = modal.App(app_name, image=image)


@lru_cache(maxsize=128)
def get_esm2_modal_class(esm_app_name: str, app_username: str):
    """Get cached user-specific ESM2 Modal class instance for billing attribution."""
    try:
        ESM2Model = modal.Cls.from_name(esm_app_name, "ESM2Model")
        return ESM2Model(app_username=app_username)
    except Exception as e:
        raise RuntimeError(f"Cannot reach ESM2 model '{esm_app_name}': {e}") from e


@app.cls(
    image=image,
    secrets=[cloudflare_r2_secret, redis_url_secret],
    enable_memory_snapshot=True,  # Enable Modal memory snapshots for faster cold starts
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class TemproModel(BillingMixinSnap):
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

        print(f"🔧 Loading TEMPRO {self.esm2_size} model for snapshot...")

        # Set deterministic behavior for consistent results
        tf.random.set_seed(42)

        # Get model directory and load Keras model
        model_dir = get_model_dir(self.esm2_size)
        model_path = model_dir / "saved_models" / f"ESM_{self.esm2_size.upper()}.keras"

        print(f"📂 Loading Keras model from: {model_path}")
        self.keras_model = keras.models.load_model(model_path)

        # ESM2 configuration - layer to extract embeddings from
        self.esm_layer = TEMPRO_ESM_LAYER_MAPPING[TemproESM2Sizes(self.esm2_size)]

        print(f"✅ TEMPRO {self.esm2_size} model loaded into memory snapshot")

    @modal.enter(snap=False)
    def setup_model(self):
        """Post-snapshot setup."""
        print(f"✅ TEMPRO {self.esm2_size} ready for inference from memory snapshot!")
        print(f"🎯 Using ESM2 layer {self.esm_layer} for embeddings")

    def get_esm2_embeddings(self, sequences: list[str]) -> "np.ndarray":
        """
        Call ESM2 via Modal function lookup to get embeddings.

        Args:
            sequences: List of protein sequences to encode

        Returns:
            numpy array of mean-pooled embeddings, shape (batch_size, embedding_dim)
        """
        print(f"🔗 Calling ESM2 for {len(sequences)} sequences...")

        # Prepare request for ESM2
        request_payload = ESM2EncodeRequest(
            params=ESM2EncodeRequestParams(
                repr_layers=[self.esm_layer], include=[ESM2EncodeIncludeOptions.MEAN]
            ),
            items=[ESM2EncodeRequestItem(sequence=seq) for seq in sequences],
        )

        # Get ESM2 model using Modal function lookup with username for billing
        esm_app_name = f"esm2-{self.esm2_size}"
        print(f"📞 Looking up ESM2 app: {esm_app_name} for user: {self.app_username}")

        try:
            # Get cached ESM2 Modal class instance with proper username attribution
            model_instance = get_esm2_modal_class(esm_app_name, self.app_username)

            # Call ESM2 remotely
            with modal.enable_output():
                response = model_instance.encode.remote(request_payload)

            # # If response is a Pydantic v2 object, convert to dict
            # if hasattr(response, "model_dump"):
            #     response = response.model_dump()

            # Everything is now a dict
            results = response["results"]
            print(f"✅ ESM2 call successful, got {len(results)} results")

            # Extract embeddings - results is a list of dicts
            embeddings = []
            for i, result in enumerate(results):
                # result is a dict, embeddings is a list of dicts
                embeddings_data = result["embeddings"]
                if not embeddings_data:
                    raise ValueError(f"No embeddings returned for sequence index {i}")

                # Get the first (and only) layer's embedding
                layer_embedding = embeddings_data[0]
                embeddings.append(layer_embedding["embedding"])

            import numpy as np

            return np.array(embeddings, dtype=np.float32)

        except Exception as e:
            print(f"❌ Error calling ESM2: {e}")
            raise RuntimeError(f"Failed to get ESM2 embeddings: {e}") from e

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def predict(self, payload: TemproPredictRequest) -> TemproPredictResponse:
        """
        Predict melting temperatures for nanobody sequences.
        """
        sequences = [item.sequence for item in payload.items]

        print(
            f"🌡️ Predicting Tm for {len(sequences)} sequences using TEMPRO {self.esm2_size}"
        )

        try:
            import numpy as np

            # Step 1: Get ESM2 embeddings
            embeddings = self.get_esm2_embeddings(sequences)
            print(f"📊 Got embeddings shape: {embeddings.shape}")

            # Step 2: Predict using Keras model
            print("🧠 Running Keras model prediction...")
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

                print(f"  Sequence {i+1}: Tm = {tm_value:.2f}°C")

            print(f"✅ TEMPRO prediction complete for {len(results)} sequences")
            return TemproPredictResponse(results=results)

        except Exception as e:
            print(f"❌ TEMPRO prediction failed: {e}")
            raise e


if __name__ == "__main__":
    """
    Usage:
        ESM2_SIZE="650m" python models/tempro/app.py
        ESM2_SIZE="3b" python models/tempro/app.py

        # Force deploy to QA or production:
        ESM2_SIZE="650m" python models/tempro/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        TemproModel,
        description=f"Run and optionally deploy the {TemproParams.display_name} {esm2_size} Modal app.",
    )
