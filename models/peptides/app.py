import modal

from models.commons.model.base import ModelMixinSnap
from models.commons.core.decorator import modal_endpoint
from models.commons.modal.source import setup_source_layer
from models.commons.model.config import biolm_model_class
from models.commons.util.config import (
    cloudflare_r2_secret,
    common_requirements,
)
from models.peptides.config import (
    MODEL_FAMILY,
    PEPTIDES_NUMERIC_FEATURES,
    PEPTIDES_VECTOR_FEATURES,
)
from models.peptides.schema import (
    PeptidesEncodeIncludeOptions,
    PeptidesEncodeRequest,
    PeptidesEncodeResponse,
    PeptidesEncodeResponseResult,
    PeptidesParams,
)

# Build Modal container image
image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .uv_pip_install("peptides==0.3.4")
)
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)


# Define the app
app_name, modal_resource_spec = MODEL_FAMILY.get_app_config()
print(f"App name: {app_name}")
app = modal.App(app_name, image=image)


@app.cls(
    image=image,
    secrets=[cloudflare_r2_secret],
    enable_memory_snapshot=True,
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class PeptidesModel(ModelMixinSnap):
    app_username: str = modal.parameter(default="default_user")

    @modal.enter(snap=True)
    def load_model(self):
        import peptides

        self.peptides = peptides

    @modal.enter(snap=False)
    def setup_model(self):
        print(
            f"✅ {PeptidesParams.display_name} model ready for inference on from memory snapshot!"
        )

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def encode(self, payload: PeptidesEncodeRequest) -> PeptidesEncodeResponse:
        """
        Compute numeric features for each sequence.
        If 'vector' is in payload.params.include, we also compute the vector-based features.
        """
        sequences = [item.sequence for item in payload.items]
        include_vectors = PeptidesEncodeIncludeOptions.VECTOR in (
            payload.params.include if payload.params else []
        )
        results = [self._compute_peptides(seq, include_vectors) for seq in sequences]
        return PeptidesEncodeResponse(results=results)

    @staticmethod
    def _convert_value(obj):
        import numpy as np

        if isinstance(obj, np.floating):
            return float(np.float32(obj))
        elif isinstance(obj, list):
            return [PeptidesModel._convert_value(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: PeptidesModel._convert_value(v) for k, v in obj.items()}
        return obj

    def _compute_peptides(
        self, seq: str, include_vectors: bool
    ) -> PeptidesEncodeResponseResult:
        """
        Actually compute the features for a single sequence.
        """
        pep_obj = self.peptides.Peptide(seq)

        pep_features = (
            PEPTIDES_NUMERIC_FEATURES + PEPTIDES_VECTOR_FEATURES
            if include_vectors
            else PEPTIDES_NUMERIC_FEATURES
        )

        features = {}
        for feature_name in pep_features:
            val = getattr(pep_obj, feature_name)()
            # Some features return dict, some named tuples, some floats, some strings, etc.
            if feature_name == "descriptors":
                # Flatten the descriptors dict directly and convert any numpy floats
                features.update(self.__class__._convert_value(val))
            elif feature_name == "frequencies":
                # Rename AA freq keys and convert any numpy floats
                freq_renamed = {
                    f"{k}_frequency": self.__class__._convert_value(v)
                    for k, v in val.items()
                }
                features.update(freq_renamed)
            else:
                # Just store the raw value after converting any numpy floats
                features[feature_name] = self.__class__._convert_value(val)

        # If vector features are included, some of them return arrays.
        # Convert them to lists and ensure all numpy floats are converted.
        if include_vectors:
            for vf in PEPTIDES_VECTOR_FEATURES:
                if vf in features and features[vf] is not None:
                    features[vf] = self.__class__._convert_value(list(features[vf]))

        return PeptidesEncodeResponseResult(features=features)


if __name__ == "__main__":
    """
    Usage:
        python models/peptides/app.py

        # Force deploy to QA or main:
        python models/peptides/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        PeptidesModel,
        description=f"Run and optionally deploy the {PeptidesParams.display_name} Modal app.",
    )
