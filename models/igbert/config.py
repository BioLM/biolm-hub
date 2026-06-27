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
from models.igbert.schema import (
    IgBertEncodeRequest,
    IgBertEncodeResponse,
    IgBertGenerateRequest,
    IgBertGenerateResponse,
    IgBertLogProbRequest,
    IgBertLogProbResponse,
    IgBertModelTypes,
    IgBertParams,
)

### Static configuration values
model_id_mapping = {
    IgBertModelTypes.UNPAIRED: "IgBert_unpaired",
    IgBertModelTypes.PAIRED: "IgBert",
}


### IgBert Modal Resource Specs

IgBert_VARIANT_RESOURCE_SPECS = {
    IgBertModelTypes.PAIRED: ModalResourceSpec(
        cpu=3.0, memory=6 * 1024, gpu=ModalGPU.T4  # 6GB RAM
    ),
    IgBertModelTypes.UNPAIRED: ModalResourceSpec(
        cpu=3.0, memory=6 * 1024, gpu=ModalGPU.T4  # 6GB RAM
    ),
}


# IgBert configuration:
# - Axes: MODEL_TYPE (paired, unpaired)
# - Actions: encode, generate, log_prob
MODEL_FAMILY = ModelFamily(
    base_model_slug=IgBertParams.base_model_slug,
    display_name=IgBertParams.display_name,
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE],
        input_molecule=[InputMolecule.ANTIBODY],
        task=[Task.EMBEDDING, Task.SEQUENCE_COMPLETION],
        output_modality=[
            OutputModality.EMBEDDING,
            OutputModality.LOGITS,
            OutputModality.SEQUENCE,
        ],
        architecture=[Architecture.TRANSFORMER, Architecture.BERT],
    ),
    # Three actions: encode, generate, and log_prob
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.ENCODE,
            request_schema=IgBertEncodeRequest,
            response_schema=IgBertEncodeResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.GENERATE,
            request_schema=IgBertGenerateRequest,
            response_schema=IgBertGenerateResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.LOG_PROB,
            request_schema=IgBertLogProbRequest,
            response_schema=IgBertLogProbResponse,
        ),
    ],
    # Single axis: MODEL_TYPE with values paired, unpaired
    variant_axes={
        "MODEL_TYPE": list(IgBertModelTypes),
    },
    # Resource function looks up the correct spec from the schema
    resource_function=lambda cfg: IgBert_VARIANT_RESOURCE_SPECS[
        IgBertModelTypes(cfg["MODEL_TYPE"])
    ],
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Multi-variant: both return "igbert-{variant}"
    naming_function=lambda base_slug, cfg: (
        f"{base_slug}-{cfg['MODEL_TYPE']}" if cfg else base_slug,
        f"{base_slug}-{cfg['MODEL_TYPE']}" if cfg else base_slug,
    ),
)
