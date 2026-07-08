from models.antifold.schema import (
    AntiFoldEncodeRequest,
    AntiFoldEncodeResponse,
    AntiFoldGenerateRequest,
    AntiFoldGenerateResponse,
    AntiFoldLogProbResponse,
    AntiFoldParams,
    AntiFoldPredictRequest,
    AntiFoldScoreResponse,
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

### Static configuration values
antifold_commit_hash = (
    "c306ae678bded89f4daa6d431ebdc72381474ccb"  # AntiFold GitHub commit
)


### AntiFold Modal Resource Specs

AntiFoldResourceSpec = ModalResourceSpec(cpu=1.0, memory=2 * 1024, gpu=None)  # 2GB RAM


# AntiFold configuration:
# - Axes: None (single variant)
# - Actions: encode, generate, score, log_prob
MODEL_FAMILY = ModelFamily(
    base_model_slug=AntiFoldParams.base_model_slug,
    display_name=AntiFoldParams.display_name,
    # The @biolm_model_class container class in app.py drives gateway routing.
    modal_class_name="AntiFoldModel",
    tags=ModelTags(
        input_modality=[InputModality.STRUCTURE],
        input_molecule=[InputMolecule.ANTIBODY, InputMolecule.NANOBODY],
        task=[Task.INVERSE_FOLDING, Task.EMBEDDING],
        output_modality=[
            OutputModality.SEQUENCE,
            OutputModality.EMBEDDING,
            OutputModality.LOGITS,
        ],
        architecture=[Architecture.GNN, Architecture.AUTOREGRESSIVE],
    ),
    # Define all public API actions
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.ENCODE,
            request_schema=AntiFoldEncodeRequest,
            response_schema=AntiFoldEncodeResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.GENERATE,
            request_schema=AntiFoldGenerateRequest,
            response_schema=AntiFoldGenerateResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.SCORE,
            request_schema=AntiFoldPredictRequest,
            response_schema=AntiFoldScoreResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.LOG_PROB,
            request_schema=AntiFoldPredictRequest,
            response_schema=AntiFoldLogProbResponse,
        ),
    ],
    # No variant axes - single variant model
    variant_axes={},
    # Resource function for single variant
    resource_function=lambda cfg: AntiFoldResourceSpec,
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Single variant: both return "antifold"
    naming_function=lambda base_slug, cfg: (base_slug, base_slug),
)
