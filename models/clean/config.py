from models.clean.schema import (
    CLEANEncodeRequest,
    CLEANEncodeResponse,
    CLEANParams,
    CLEANPredictRequest,
    CLEANPredictResponse,
)
from models.commons.model.config import ActionSchemaMap, ModelFamily
from models.commons.model.schema import ModalGPU, ModalResourceSpec, ModelActions
from models.commons.model.tag import (
    Architecture,
    InputModality,
    InputMolecule,
    ModelTags,
    OutputModality,
    Task,
)

# CLEAN Modal Resource Specs
# ESM-1b (650M) requires ~2.5GB VRAM, T4 has 16GB
CLEANResourceSpec = ModalResourceSpec(
    cpu=4.0,
    memory=16 * 1024,  # 16GB RAM
    gpu=ModalGPU.T4,
)

# CLEAN configuration:
# - Axes: None (single variant using split100)
# - Actions: predict, encode
MODEL_FAMILY = ModelFamily(
    base_model_slug=CLEANParams.base_model_slug,
    display_name=CLEANParams.display_name,
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE],
        input_molecule=[InputMolecule.PROTEIN],
        task=[Task.PROPERTY_PREDICTION, Task.EMBEDDING],
        output_modality=[OutputModality.CLASS_LABEL, OutputModality.EMBEDDING],
        architecture=[Architecture.TRANSFORMER],
    ),
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.PREDICT,
            request_schema=CLEANPredictRequest,
            response_schema=CLEANPredictResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.ENCODE,
            request_schema=CLEANEncodeRequest,
            response_schema=CLEANEncodeResponse,
        ),
    ],
    # No variants - single deployment using split100
    variant_axes={},
    # Static resource function for single variant
    resource_function=lambda cfg: CLEANResourceSpec,
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    naming_function=lambda base_slug, cfg: (base_slug, base_slug),
)
