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
from models.nanobert.schema import (
    NanoBERTEncodeRequest,
    NanoBERTEncodeResponse,
    NanoBERTGenerateRequest,
    NanoBERTGenerateResponse,
    NanoBERTLogProbRequest,
    NanoBERTLogProbResponse,
    NanoBERTParams,
)

### NanoBERT Modal Resource Specs

NanoBERTResourceSpec = ModalResourceSpec(cpu=2.0, memory=2 * 1024, gpu=None)  # 2GB Ram


# NanoBERT configuration:
# - Axes: None (single variant)
# - Actions: encode, generate, log_prob
MODEL_FAMILY = ModelFamily(
    base_model_slug=NanoBERTParams.base_model_slug,
    display_name=NanoBERTParams.display_name,
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE],
        input_molecule=[InputMolecule.NANOBODY],
        task=[Task.EMBEDDING, Task.SEQUENCE_COMPLETION, Task.PROPERTY_PREDICTION],
        output_modality=[
            OutputModality.EMBEDDING,
            OutputModality.SEQUENCE,
            OutputModality.LOG_PROBABILITIES,
        ],
        architecture=[Architecture.TRANSFORMER, Architecture.BERT],
    ),
    # Three actions: encode, generate, log_prob
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.ENCODE,
            request_schema=NanoBERTEncodeRequest,
            response_schema=NanoBERTEncodeResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.GENERATE,
            request_schema=NanoBERTGenerateRequest,
            response_schema=NanoBERTGenerateResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.LOG_PROB,
            request_schema=NanoBERTLogProbRequest,
            response_schema=NanoBERTLogProbResponse,
        ),
    ],
    # No variants - single deployment
    variant_axes={},
    # Resource function - single static resource spec
    resource_function=lambda cfg: NanoBERTResourceSpec,
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Single variant: both return "nanobert"
    naming_function=lambda base_slug, cfg: (base_slug, base_slug),
)
