from typing import Any

import modal
from modal import Cls

from models.commons.model.base import ModelMixin
from models.commons.core.decorator import modal_endpoint
from models.commons.modal.downloader import setup_download_layer
from models.commons.modal.source import setup_source_layer
from models.commons.model.config import biolm_model_class
from models.commons.util.config import (
    cloudflare_r2_secret,
    common_requirements,
)
from models.esm2.schema import (
    ESM2EncodeIncludeOptions,
    ESM2EncodeRequest,
    ESM2EncodeRequestItem,
    ESM2EncodeRequestParams,
)
from models.esmstabp.config import MODEL_FAMILY
from models.esmstabp.download import get_model_dir
from models.esmstabp.schema import (
    ESMStabPParams,
    ESMStabPPredictRequest,
    ESMStabPPredictResponse,
    ESMStabPPredictResponseResult,
)

# Build Modal container image
# Using slim Python image since no GPU needed (ESM2 runs on separate endpoint)
image = modal.Image.debian_slim(python_version="3.12")

# Setup download layer with model weights (Random Forest joblib files)
image = setup_download_layer(
    image,
    base_model_slug=ESMStabPParams.base_model_slug,
    params_version=ESMStabPParams.params_version,
    variant_config={},
)

# Add dependencies and packages
# Note: No ESM2 or PyTorch needed - embeddings obtained via Modal function call
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .uv_pip_install(
        # scikit-learn for Random Forest inference
        "scikit-learn==1.3.2",
        # joblib for model loading
        "joblib==1.3.2",
        # numpy for array operations
        "numpy==1.26.4",
    )
)

# Finally, add all model files
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)

# Define the app using unified config
app_name, modal_resource_spec = MODEL_FAMILY.get_app_config()
print(f"App name: {app_name}")
app = modal.App(app_name, image=image)


@app.cls(
    image=image,
    secrets=[cloudflare_r2_secret],
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class ESMStabPModel(ModelMixin):
    app_username: str = modal.parameter(default="default_user")

    """
    ESMStabPModel predicts protein melting temperatures (Tm) using:
     - ESM2 layer 33 embeddings (via esm2-650m endpoint)
     - Random Forest regressor (CPU-only)
    """

    @modal.enter()
    def setup_model(self) -> None:
        """Load RF models and initialize ESM2 endpoint reference."""
        import joblib
        import numpy as np

        print("Loading ESMStabP model...")
        np.random.seed(42)
        self.np = np
        self.model_dir = get_model_dir()
        self.max_sequence_len = ESMStabPParams.max_sequence_len

        # ESM2 endpoint reference (lightweight, no model loading)
        print("Initializing ESM2 endpoint reference...")
        self.esm2_model = Cls.from_name("esm2-650m", "ESM2Model")(
            app_username=self.app_username
        )

        # Load Random Forest models
        print("Loading Random Forest models...")
        self.rf_models: dict[int, Any] = {}
        for model_num in [1, 2, 3, 4]:
            model_path = self.model_dir / f"{model_num}.joblib"
            if model_path.exists():
                self.rf_models[model_num] = joblib.load(model_path)
                print(f"  Loaded {model_num}.joblib")
            else:
                print(f"  Warning: {model_num}.joblib not found")

        if not self.rf_models:
            raise RuntimeError("No RF models found. Upload joblib files to R2.")

        print("ESMStabP model loaded!")

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def predict(self, payload: ESMStabPPredictRequest) -> ESMStabPPredictResponse:
        """Predict protein melting temperatures (Tm) from sequences."""
        print(f"ESMStabP predict called with {len(payload.items)} sequences")

        # Batch ESM2 embeddings (single RPC for all sequences)
        sequences = [item.sequence for item in payload.items]
        embeddings = self._extract_embeddings_batch(sequences)

        results = []
        for i, item in enumerate(payload.items):
            model_num, features = self._prepare_features(
                embeddings[i],
                growth_temp=item.growth_temp,
                experimental_condition=(
                    item.experimental_condition.value
                    if item.experimental_condition
                    else None
                ),
            )

            if model_num not in self.rf_models:
                raise RuntimeError(
                    f"RF model {model_num}.joblib not found. "
                    f"Run: python models/esmstabp/_train.py"
                )

            tm_pred = self.rf_models[model_num].predict([features])[0]
            results.append(
                ESMStabPPredictResponseResult(
                    melting_temperature=float(tm_pred),
                    is_thermophilic=bool(tm_pred > 60.0),
                )
            )

        print(f"ESMStabP predict completed for {len(results)} sequences")
        return ESMStabPPredictResponse(results=results)

    def _extract_embeddings_batch(self, sequences: list[str]) -> list[list[float]]:
        """Batch extract ESM2 layer 33 mean embeddings via single RPC call."""
        request = ESM2EncodeRequest(
            params=ESM2EncodeRequestParams(
                repr_layers=[33],
                include=[ESM2EncodeIncludeOptions.MEAN],
            ),
            items=[ESM2EncodeRequestItem(sequence=seq) for seq in sequences],
        )

        try:
            response = self.esm2_model.encode.remote(request.model_dump())
        except Exception as e:
            raise RuntimeError(f"ESM2 endpoint call failed: {e}") from e

        try:
            return [r["embeddings"][0]["embedding"] for r in response["results"]]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected ESM2 response: {e}") from e

    def _prepare_features(
        self,
        embedding: list[float],
        growth_temp: int | None = None,
        experimental_condition: str | None = None,
    ) -> tuple[int, list[float]]:
        """Prepare feature vector and select RF model based on available metadata."""
        features = self.np.array(embedding)
        has_growth_temp = growth_temp is not None
        has_condition = experimental_condition is not None

        if has_growth_temp and has_condition:
            # Model 4: embedding + growth_temp + lysate + cell + thermophilic + nonThermophilic
            assert growth_temp is not None
            features = self.np.append(features, growth_temp)
            features = self.np.append(
                features, 1 if experimental_condition == "lysate" else 0
            )
            features = self.np.append(
                features, 1 if experimental_condition == "cell" else 0
            )
            features = self.np.append(features, 1 if growth_temp > 60 else 0)
            features = self.np.append(features, 1 if growth_temp < 30 else 0)
            return 4, features.tolist()

        elif has_growth_temp:
            # Model 2: embedding + growth_temp + thermophilic + nonThermophilic
            assert growth_temp is not None
            features = self.np.append(features, growth_temp)
            features = self.np.append(features, 1 if growth_temp > 60 else 0)
            features = self.np.append(features, 1 if growth_temp < 30 else 0)
            return 2, features.tolist()

        elif has_condition:
            # Model 3: embedding + lysate + cell
            features = self.np.append(
                features, 1 if experimental_condition == "lysate" else 0
            )
            features = self.np.append(
                features, 1 if experimental_condition == "cell" else 0
            )
            return 3, features.tolist()

        else:
            # Model 1: embedding only
            return 1, features.tolist()


if __name__ == "__main__":
    """
    Usage:
        python models/esmstabp/app.py

        # Force deploy to "qa" or "main" environment:
        python models/esmstabp/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        ESMStabPModel,
        description=f"Run and optionally deploy the {ESMStabPParams.display_name} Modal app.",
    )
