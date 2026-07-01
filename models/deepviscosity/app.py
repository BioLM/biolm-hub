from typing import Literal

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
from models.deepviscosity.config import MODEL_FAMILY
from models.deepviscosity.download import get_model_dir
from models.deepviscosity.schema import (
    DEEPSP_FEATURE_NAMES,
    DeepViscosityParams,
    DeepViscosityPredictRequest,
    DeepViscosityPredictResponse,
    DeepViscosityPredictResponseResult,
)
from models.deepviscosity.util import load_scaler

logger = get_logger(__name__)

# Build Modal container image (micromamba for bioconda packages, Python 3.10 for TF 2.11)
image = modal.Image.micromamba(python_version="3.10")
# Setup download layer with model weights (early for layer caching)
image = setup_download_layer(
    image,
    base_model_slug=DeepViscosityParams.base_model_slug,
    weights_version=DeepViscosityParams.weights_version,
    variant_config={},
)
# Add dependencies and packages
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .micromamba_install(
        "anarci",
        "hmmer=3.3.2",
        channels=["conda-forge", "bioconda"],
    )
    .uv_pip_install(common_requirements)
    .uv_pip_install(
        "tensorflow-cpu==2.11.0",
        "keras==2.11.0",
        "h5py==3.7.0",
        "scikit-learn==1.0.2",
        "numpy==1.23.5",
        "scipy==1.10.1",
        "pandas==1.5.3",
        "biopython==1.80",
        "joblib==1.1.1",
    )
)
# Finally, add all model files
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)

# Define the app
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
class DeepViscosityModel(ModelMixinSnap):
    """
    DeepViscosity model for predicting monoclonal antibody viscosity.

    Uses 102 ensemble ANN models with DeepSP spatial features to classify
    antibody viscosity as low (<=20 cP) or high (>20 cP) at 150 mg/mL.
    """

    app_username: str = modal.parameter(default="default_user")

    @modal.enter(snap=True)
    def load_model(self) -> None:
        """Load all models during snapshot creation."""
        import os

        import tensorflow as tf
        from tensorflow.keras.models import model_from_json

        # Suppress TF warnings
        os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
        os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

        logger.info("Loading DeepViscosity models...")

        # Set deterministic seeds
        np.random.seed(42)
        tf.random.set_seed(42)

        self.model_dir = get_model_dir()
        logger.info("Model directory: %s", self.model_dir)

        # Load DeepSP CNN models for feature generation
        logger.info("Loading DeepSP CNN models...")
        self.deepsp_models = {}

        cnn_dir = self.model_dir / "DeepSP_CNN_model"
        for model_name, json_file, h5_file in [
            ("SAPpos", "Conv1D_regressionSAPpos.json", "Conv1D_regression_SAPpos.h5"),
            ("SCMneg", "Conv1D_regressionSCMneg.json", "Conv1D_regression_SCMneg.h5"),
            ("SCMpos", "Conv1D_regressionSCMpos.json", "Conv1D_regression_SCMpos.h5"),
        ]:
            json_path = cnn_dir / json_file
            h5_path = cnn_dir / h5_file

            with open(json_path) as f:
                model = model_from_json(f.read())
            model.load_weights(str(h5_path))
            model.compile(optimizer="adam", loss="mae", metrics=["mae"])
            self.deepsp_models[model_name] = model
            logger.debug("  Loaded %s", model_name)

        # Load StandardScaler from embedded parameters
        logger.info("Loading feature scaler...")
        self.scaler = load_scaler()

        # Load 102 ensemble ANN models
        logger.info("Loading ensemble ANN models...")
        self.ensemble_models = []
        ensemble_dir = self.model_dir / "DeepViscosity_ANN_ensemble_models"

        for i in range(102):
            json_path = ensemble_dir / f"ANN_logo_{i}.json"
            h5_path = ensemble_dir / f"ANN_logo_{i}.h5"

            with open(json_path) as f:
                model = model_from_json(f.read())
            model.load_weights(str(h5_path))
            # No compile needed for inference-only use
            self.ensemble_models.append(model)

        logger.info("  Loaded %s ensemble models", len(self.ensemble_models))
        logger.info("DeepViscosity models loaded successfully!")

    @modal.enter(snap=False)
    def setup_model(self) -> None:
        """Called after restoring from snapshot."""
        logger.info("%s ready for inference!", DeepViscosityParams.display_name)

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def predict(
        self, payload: DeepViscosityPredictRequest
    ) -> DeepViscosityPredictResponse:
        """Predict antibody viscosity class from VH/VL sequences."""
        from models.deepviscosity.util import align_and_encode

        logger.info(
            "DeepViscosity predict called with %s antibodies", len(payload.items)
        )

        # Check if we should include DeepSP features in response
        include_features = False
        if payload.params:
            include_features = payload.params.include_deepsp_features

        results = []
        for item in payload.items:
            # 1. Align sequences and one-hot encode
            encoded = align_and_encode(item.heavy_chain, item.light_chain)
            # Add batch dimension: (272, 21) -> (1, 272, 21)
            encoded_batch = np.expand_dims(encoded, axis=0)

            # 2. Generate DeepSP features via CNN models
            sap_pos = self.deepsp_models["SAPpos"].predict(encoded_batch, verbose=0)
            scm_neg = self.deepsp_models["SCMneg"].predict(encoded_batch, verbose=0)
            scm_pos = self.deepsp_models["SCMpos"].predict(encoded_batch, verbose=0)

            # Concatenate features: [SAP_pos(10), SCM_neg(10), SCM_pos(10)] = 30 features
            deepsp_features = np.concatenate(
                [sap_pos[0], scm_neg[0], scm_pos[0]], axis=0
            )

            # 3. Scale features
            scaled_features = self.scaler.transform([deepsp_features])

            # 4. Run through 102 ensemble models
            predictions = []
            for model in self.ensemble_models:
                pred = model.predict(scaled_features, verbose=0)
                predictions.append(pred[0][0])

            # 5. Aggregate predictions
            prob_mean = float(np.mean(predictions))
            prob_std = float(np.std(predictions))
            is_high = prob_mean >= 0.5
            viscosity_class: Literal["low", "high"] = "high" if is_high else "low"

            # Build response
            result = DeepViscosityPredictResponseResult(
                viscosity_class=viscosity_class,
                probability_mean=round(prob_mean, 6),
                probability_std=round(prob_std, 6),
                is_high_viscosity=is_high,
            )

            # Include DeepSP features if requested
            if include_features:
                if len(DEEPSP_FEATURE_NAMES) != len(deepsp_features):
                    raise ServerError(
                        "DeepSP feature count mismatch: "
                        f"expected {len(DEEPSP_FEATURE_NAMES)}, "
                        f"got {len(deepsp_features)}"
                    )
                result.deepsp_features = {
                    name: round(float(val), 6)
                    for name, val in zip(
                        DEEPSP_FEATURE_NAMES, deepsp_features, strict=False
                    )
                }

            results.append(result)

        logger.info("DeepViscosity predict completed for %s antibodies", len(results))
        return DeepViscosityPredictResponse(results=results)


if __name__ == "__main__":
    """
    Usage:
        python models/deepviscosity/app.py

        # Force deploy to biolm-hub-dev or biolm-hub:
        python models/deepviscosity/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        DeepViscosityModel,
        description=f"Run and optionally deploy the {DeepViscosityParams.display_name} Modal app.",
    )
