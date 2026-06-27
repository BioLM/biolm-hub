from models.ablang2.schema import (
    AbLang2EncodeRequest,
    AbLang2GenerateRequest,
    AbLang2GenerateResponse,
    AbLang2LogProbRequest,
    AbLang2LogProbResponse,
    AbLang2Params,
    AbLang2PredictRequest,
    AbLang2PredictResponse,
    AbLang2SeqcodingResponse,
)
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

# Static configuration values
N_CPUS = 4  # Number of CPUs for model loading

### AbLang2 Modal Resource Specs

AbLang2ResourceSpec = ModalResourceSpec(
    cpu=2.0,
    memory=4 * 1024,  # 4GB
    gpu=None,
)


# AbLang2 configuration:
# - Axes: None (single variant)
# - Actions: encode, predict, generate, predict_log_prob
MODEL_FAMILY = ModelFamily(
    base_model_slug=AbLang2Params.base_model_slug,
    display_name=AbLang2Params.display_name,
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE],
        input_molecule=[InputMolecule.ANTIBODY],
        task=[Task.EMBEDDING, Task.SEQUENCE_COMPLETION, Task.PROPERTY_PREDICTION],
        output_modality=[
            OutputModality.EMBEDDING,
            OutputModality.SEQUENCE,
            OutputModality.LOG_PROBABILITIES,
        ],
        architecture=[Architecture.TRANSFORMER, Architecture.BERT],
    ),
    # Define all public API actions
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.ENCODE,
            request_schema=AbLang2EncodeRequest,
            response_schema=AbLang2SeqcodingResponse,  # Primary response type
        ),
        ActionSchemaMap(
            name=ModelActions.PREDICT,
            request_schema=AbLang2PredictRequest,
            response_schema=AbLang2PredictResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.GENERATE,
            request_schema=AbLang2GenerateRequest,
            response_schema=AbLang2GenerateResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.PREDICT_LOG_PROB,
            request_schema=AbLang2LogProbRequest,
            response_schema=AbLang2LogProbResponse,
        ),
    ],
    # No variant axes - single variant model
    variant_axes={},
    # Resource function for single variant
    resource_function=lambda cfg: AbLang2ResourceSpec,
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Single variant: both return "ablang2"
    naming_function=lambda base_slug, cfg: (base_slug, base_slug),
)
