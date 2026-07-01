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
from models.e1.schema import (
    E1EncodeRequest,
    E1EncodeResponse,
    E1LogProbRequest,
    E1LogProbResponse,
    E1ModelSizes,
    E1Params,
    E1PredictRequest,
    E1PredictResponse,
)

### Static configuration values
# HuggingFace repository mapping for E1 models
E1_HF_REPO_MAP = {
    E1ModelSizes.SIZE_150M: "Synthyra/Profluent-E1-150M",
    E1ModelSizes.SIZE_300M: "Synthyra/Profluent-E1-300M",
    E1ModelSizes.SIZE_600M: "Synthyra/Profluent-E1-600M",
}
# Pin specific revisions for reproducibility
E1_HF_REVISION_MAP = {
    E1ModelSizes.SIZE_150M: "c5845c6a08c2dcba965207974fd3cbed23bc1184",
    E1ModelSizes.SIZE_300M: "daddb06bf2e62930c0e5353c1a7d517e4db33b37",
    E1ModelSizes.SIZE_600M: "5b31cb9a229063d90fcd4c01e1eb1908fef1fbe8",
}


### E1 Modal Resource Specs

E1_VARIANT_RESOURCE_SPECS = {
    # Using float16 on T4 (native support)
    E1ModelSizes.SIZE_150M: ModalResourceSpec(
        cpu=3,
        memory=8 * 1024,  # 8 GB
        gpu=ModalGPU.T4,
    ),
    # E1-300M/600M use bfloat16 on L4 (native Ada Lovelace support, 27% cheaper than A10G)
    E1ModelSizes.SIZE_300M: ModalResourceSpec(
        cpu=4,
        memory=16 * 1024,  # 16 GB
        gpu=ModalGPU.L4,
    ),
    E1ModelSizes.SIZE_600M: ModalResourceSpec(
        cpu=4,
        memory=24 * 1024,  # 24 GB
        gpu=ModalGPU.L4,
    ),
}


# E1 configuration:
# - Axes: MODEL_SIZE (150m, 300m, 600m)
# - Actions: encode, predict, log_prob
MODEL_FAMILY = ModelFamily(
    base_model_slug=E1Params.base_model_slug,
    modal_class_name="E1Model",
    display_name=E1Params.display_name,
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
            request_schema=E1EncodeRequest,
            response_schema=E1EncodeResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.PREDICT,
            request_schema=E1PredictRequest,
            response_schema=E1PredictResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.LOG_PROB,
            request_schema=E1LogProbRequest,
            response_schema=E1LogProbResponse,
        ),
    ],
    # Single axis: MODEL_SIZE with values 150m, 300m, 600m
    variant_axes={
        "MODEL_SIZE": list(E1ModelSizes),
    },
    # Resource function looks up the correct spec from the schema
    resource_function=lambda cfg: E1_VARIANT_RESOURCE_SPECS[
        E1ModelSizes(cfg["MODEL_SIZE"])
    ],
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Multi-variant: both return "e1-{variant}"
    naming_function=lambda base_slug, cfg: (
        f"{base_slug}-{cfg['MODEL_SIZE']}" if cfg else base_slug,
        f"{base_slug}-{cfg['MODEL_SIZE']}" if cfg else base_slug,
    ),
)
