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
from models.esm2.schema import (
    ESM2EncodeRequest,
    ESM2EncodeResponse,
    ESM2LogProbRequest,
    ESM2LogProbResponse,
    ESM2ModelSizes,
    ESM2Params,
    ESM2PredictRequest,
    ESM2PredictResponse,
)

### ESM2 Modal Resource Specs

ESM2_VARIANT_RESOURCE_SPECS = {
    ESM2ModelSizes.SIZE_8M: ModalResourceSpec(
        cpu=2.0, memory=8 * 1024, gpu=None  # 8GB RAM
    ),
    ESM2ModelSizes.SIZE_35M: ModalResourceSpec(
        cpu=2.0, memory=8 * 1024, gpu=None  # 8GB RAM
    ),
    ESM2ModelSizes.SIZE_150M: ModalResourceSpec(
        cpu=4.0, memory=16 * 1024, gpu=ModalGPU.T4  # 16GB RAM
    ),
    ESM2ModelSizes.SIZE_650M: ModalResourceSpec(
        cpu=4.0, memory=16 * 1024, gpu=ModalGPU.T4  # 16GB RAM
    ),
    ESM2ModelSizes.SIZE_3B: ModalResourceSpec(
        cpu=4.0, memory=32 * 1024, gpu=ModalGPU.L40S  # 32GB RAM, 48GB VRAM
    ),
}


model_id_mapping = {
    ESM2ModelSizes.SIZE_8M: "esm2_t6_8M_UR50D",
    ESM2ModelSizes.SIZE_35M: "esm2_t12_35M_UR50D",
    ESM2ModelSizes.SIZE_150M: "esm2_t30_150M_UR50D",
    ESM2ModelSizes.SIZE_650M: "esm2_t33_650M_UR50D",
    ESM2ModelSizes.SIZE_3B: "esm2_t36_3B_UR50D",
}

# ESM2 configuration:
# - Axes: MODEL_SIZE (8m, 35m, 150m, 650m, 3b)
# - Actions: encode, predict, log_prob
MODEL_FAMILY = ModelFamily(
    base_model_slug=ESM2Params.base_model_slug,
    display_name=ESM2Params.display_name,
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
            request_schema=ESM2EncodeRequest,
            response_schema=ESM2EncodeResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.PREDICT,
            request_schema=ESM2PredictRequest,
            response_schema=ESM2PredictResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.LOG_PROB,
            request_schema=ESM2LogProbRequest,
            response_schema=ESM2LogProbResponse,
        ),
    ],
    # Single axis: MODEL_SIZE with values 8m, 35m, 150m, 650m, 3b
    variant_axes={
        "MODEL_SIZE": list(ESM2ModelSizes),
    },
    # Resource function looks up the correct spec from the schema
    resource_function=lambda cfg: ESM2_VARIANT_RESOURCE_SPECS[
        ESM2ModelSizes(cfg["MODEL_SIZE"])
    ],
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Multi-variant: both return "esm2-8m", "esm2-35m", "esm2-150m", "esm2-650m", "esm2-3b"
    naming_function=lambda base_slug, cfg: (
        f"{base_slug}-{cfg['MODEL_SIZE']}" if cfg else base_slug,
        f"{base_slug}-{cfg['MODEL_SIZE']}" if cfg else base_slug,
    ),
)
