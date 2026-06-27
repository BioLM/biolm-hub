from models.commons.model.config import ActionSchemaMap, ModelFamily
from models.commons.model.schema import ModalResourceSpec, ModelActions
from models.commons.model.tag import (
    Architecture,
    InputModality,
    ModelTags,
    OutputModality,
    Task,
)
from models.dummy.schema import (
    DummyParams,
    DummySvcRequest,
    DummySvcResponse,
)

### Dummy Modal Resource Specs

DummyResourceSpec = ModalResourceSpec(
    cpu=0.5,
    memory=512,  # 512MB RAM
)

# Dummy configuration:
# - Axes: None (single variant)
# - Actions: inference
MODEL_FAMILY = ModelFamily(
    base_model_slug=DummyParams.base_model_slug,
    display_name=DummyParams.display_name,
    tags=ModelTags(
        input_modality=[InputModality.TEXT],
        input_molecule=[],
        task=[Task.UTILITY],
        output_modality=[OutputModality.TEXT],
        architecture=[Architecture.PLACEHOLDER],
    ),
    # Single action: predict
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.PREDICT,
            request_schema=DummySvcRequest,
            response_schema=DummySvcResponse,
        )
    ],
    # No variants - single deployment
    variant_axes={},
    # Static resource function for single variant
    resource_function=lambda cfg: DummyResourceSpec,
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Single variant: both return "dummy"
    naming_function=lambda base_slug, cfg: (base_slug, base_slug),
)
