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
from models.dnabert2.schema import (
    DNABERT2EncodeRequest,
    DNABERT2EncodeResponse,
    DNABERT2LogProbRequest,
    DNABERT2LogProbResponse,
    DNABERT2Params,
)

### Static configuration values
hf_repo_id = "zhihan1996/DNABERT-2-117M"
hf_pin_revision = "d064dece8a8b41d9fb8729fbe3435278786931f1"  # DNABERT2 HuggingFace pin


### DNABERT2 Modal Resource Specs

DNABERT2ResourceSpec = ModalResourceSpec(
    cpu=2.0,
    memory=4 * 1024,  # 4 GB
    gpu=ModalGPU.T4,
)


# DNABERT2 configuration:
# - Axes: None (single variant)
# - Actions: encode, log_prob
MODEL_FAMILY = ModelFamily(
    base_model_slug=DNABERT2Params.base_model_slug,
    modal_class_name="DNABERT2Model",
    display_name=DNABERT2Params.display_name,
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE],
        input_molecule=[InputMolecule.DNA],
        task=[Task.EMBEDDING, Task.PROPERTY_PREDICTION],
        output_modality=[OutputModality.EMBEDDING, OutputModality.LOG_PROBABILITIES],
        architecture=[Architecture.TRANSFORMER, Architecture.BERT],
    ),
    # Two actions: encode and log_prob
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.ENCODE,
            request_schema=DNABERT2EncodeRequest,
            response_schema=DNABERT2EncodeResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.LOG_PROB,
            request_schema=DNABERT2LogProbRequest,
            response_schema=DNABERT2LogProbResponse,
        ),
    ],
    # No variants - single model
    variant_axes={},
    # Single resource spec for the only variant
    resource_function=lambda cfg: DNABERT2ResourceSpec,
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Single variant: both return "dnabert2"
    naming_function=lambda base_slug, cfg: (base_slug, base_slug),
)
