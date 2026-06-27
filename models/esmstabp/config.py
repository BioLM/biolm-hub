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
from models.esmstabp.schema import (
    ESMStabPParams,
    ESMStabPPredictRequest,
    ESMStabPPredictResponse,
)

### ESMStabP Modal Resource Specs

# CPU-only: ESM2 embeddings obtained via Modal function call to esm2-650m endpoint
# Only needs resources for Random Forest inference
ESMStabPResourceSpec = ModalResourceSpec(
    cpu=2.0,
    memory=4 * 1024,  # 4GB RAM (RF inference only)
    gpu=None,  # No GPU needed - ESM2 runs on separate endpoint
)

# ESMStabP configuration:
# - Single variant (no size/type variants)
# - Single action: predict
MODEL_FAMILY = ModelFamily(
    base_model_slug=ESMStabPParams.base_model_slug,
    display_name=ESMStabPParams.display_name,
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE],
        input_molecule=[InputMolecule.PROTEIN],
        task=[Task.PROPERTY_PREDICTION, Task.STABILITY_PREDICTION],
        output_modality=[OutputModality.SCALAR],
        architecture=[Architecture.TRANSFORMER],
    ),
    # Single action: predict
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.PREDICT,
            request_schema=ESMStabPPredictRequest,
            response_schema=ESMStabPPredictResponse,
        ),
    ],
    # No variant axes (single-variant model)
    variant_axes={},
    # Resource function returns the same spec for all configs
    resource_function=lambda cfg: ESMStabPResourceSpec,
    # Naming function: single variant means just the base slug
    naming_function=lambda base_slug, cfg: (base_slug, base_slug),
)
