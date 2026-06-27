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
from models.esm1b.schema import (
    ESM1bEncodeRequest,
    ESM1bEncodeResponse,
    ESM1bLogProbRequest,
    ESM1bLogProbResponse,
    ESM1bParams,
    ESM1bPredictRequest,
    ESM1bPredictResponse,
)

### Static configuration values

# HuggingFace repository details for ESM-1b
ESM1B_HF_REPO_ID = "facebook/esm1b_t33_650M_UR50S"
# Pin to specific commit hash for reproducibility
ESM1B_HF_REVISION = "7b37824baec4d3658e1df7479222a7c79b465b76"


### ESM-1b Modal Resource Specs

ESM1b_RESOURCE_SPEC = ModalResourceSpec(
    cpu=4.0,
    memory=16 * 1024,  # 16GB RAM
    gpu=ModalGPU.T4,
)


# ESM-1b configuration:
# - Axes: None (single variant - 650M parameters)
# - Actions: encode, predict, log_prob
MODEL_FAMILY = ModelFamily(
    base_model_slug=ESM1bParams.base_model_slug,
    display_name=ESM1bParams.display_name,
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE],
        input_molecule=[InputMolecule.PROTEIN],
        task=[Task.EMBEDDING, Task.SEQUENCE_COMPLETION, Task.PROPERTY_PREDICTION],
        output_modality=[
            OutputModality.EMBEDDING,
            OutputModality.LOGITS,
            OutputModality.LOG_PROBABILITIES,
        ],
        architecture=[Architecture.TRANSFORMER],
    ),
    # Three actions: encode, predict, log_prob
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.ENCODE,
            request_schema=ESM1bEncodeRequest,
            response_schema=ESM1bEncodeResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.PREDICT,
            request_schema=ESM1bPredictRequest,
            response_schema=ESM1bPredictResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.LOG_PROB,
            request_schema=ESM1bLogProbRequest,
            response_schema=ESM1bLogProbResponse,
        ),
    ],
    # No variants - single deployment (650M parameter model)
    variant_axes={},
    # Static resource function for single variant
    resource_function=lambda cfg: ESM1b_RESOURCE_SPEC,
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Single variant: both return "esm1b"
    naming_function=lambda base_slug, cfg: (base_slug, base_slug),
)
