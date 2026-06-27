from models.commons.model.config import ActionSchemaMap, ModelFamily
from models.commons.model.schema import ModalResourceSpec, ModelActions
from models.commons.model.tag import (
    Architecture,
    InputModality,
    InputMolecule,
    ModelTags,
    OutputModality,
    Task,
)
from models.tempro.schema import (
    TemproESM2Sizes,
    TemproParams,
    TemproPredictRequest,
    TemproPredictResponse,
)

### Static configuration values
# GitHub commit version for tracking
TEMPRO_GIT_COMMIT = "d2752834f16c30df1a684304a568ad1bac036583"

# URL to the user.zip file containing all model weights
TEMPRO_ZIP_URL = (
    f"https://github.com/Jerome-Alvarez/TEMPRO/raw/{TEMPRO_GIT_COMMIT}/user.zip"
)


# ESM2 layer mapping of last layer for each model size
TEMPRO_ESM_LAYER_MAPPING = {
    TemproESM2Sizes.SIZE_650M: 33,
    TemproESM2Sizes.SIZE_3B: 36,
    # TemproESM2Sizes.SIZE_15B: 48,
}


### TEMPRO Modal Resource Specs

TEMPRO_VARIANT_RESOURCE_SPECS = {
    TemproESM2Sizes.SIZE_650M: ModalResourceSpec(
        cpu=1.0, memory=4 * 1024, gpu=None  # CPU only for Keras inference
    ),
    TemproESM2Sizes.SIZE_3B: ModalResourceSpec(
        cpu=1.0, memory=4 * 1024, gpu=None  # CPU only for Keras inference
    ),
    # TemproESM2Sizes.SIZE_15B: ModalResourceSpec(
    #     cpu=2.0, memory=8 * 1024, gpu=None  # CPU only for Keras inference
    # ),
}


# TEMPRO configuration:
# - Axes: ESM2_SIZE (650m, 3b)
# - Actions: predict (melting temperature prediction)
MODEL_FAMILY = ModelFamily(
    base_model_slug=TemproParams.base_model_slug,
    modal_class_name="TemproModel",
    display_name=TemproParams.display_name,
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE],
        input_molecule=[
            InputMolecule.NANOBODY,  # Specifically trained on nanobodies only
        ],
        task=[Task.PROPERTY_PREDICTION],
        output_modality=[OutputModality.SCALAR],
        architecture=[Architecture.TRANSFORMER],  # Uses ESM2 transformer embeddings
    ),
    # Single action: predict (melting temperature prediction)
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.PREDICT,
            request_schema=TemproPredictRequest,
            response_schema=TemproPredictResponse,
        ),
    ],
    # Single axis: ESM2_SIZE with values 650m, 3b
    variant_axes={
        "ESM2_SIZE": list(TemproESM2Sizes),
    },
    # Resource function looks up the correct spec from the schema
    resource_function=lambda cfg: TEMPRO_VARIANT_RESOURCE_SPECS[
        TemproESM2Sizes(cfg["ESM2_SIZE"])
    ],
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Multi-variant: both return "tempro-650m", "tempro-3b"
    naming_function=lambda base_slug, cfg: (
        f"{base_slug}-{cfg['ESM2_SIZE']}" if cfg else base_slug,
        f"{base_slug}-{cfg['ESM2_SIZE']}" if cfg else base_slug,
    ),
)
