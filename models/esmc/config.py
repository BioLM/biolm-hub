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
from models.esmc.schema import (
    ESMCEncodeRequest,
    ESMCEncodeResponse,
    ESMCModelSizes,
    ESMCParams,
    ESMCPredictLogProbRequest,
    ESMCPredictLogProbResponse,
    ESMCPredictRequest,
    ESMCPredictResponse,
)

### Static configuration values
# Only the 300M variant ships: the ESM C 600M weights are under EvolutionaryScale's
# Cambrian *Non-Commercial* license, so they are excluded from this open catalog
# (the 300M weights are Cambrian Open). See sources.yaml / LICENSE.
# HuggingFace repository mapping for ESMC models
ESMC_HF_REPO_MAP = {
    ESMCModelSizes.SIZE_300M: "EvolutionaryScale/esmc-300m-2024-12",
}
# Pin specific revisions for reproducibility
ESMC_HF_REVISION_MAP = {
    ESMCModelSizes.SIZE_300M: "a19d363f07313a10a64d08a2d6b41376a73df5c8",
}


### ESM C Modal Resource Specs

ESMC_VARIANT_RESOURCE_SPECS = {
    ESMCModelSizes.SIZE_300M: ModalResourceSpec(
        cpu=2.0,
        memory=24 * 1024,  # 24 GB
        gpu=ModalGPU.A10G,
    ),
}


# ESM-C configuration:
# - Axes: MODEL_SIZE (300m only; 600m excluded — non-commercial license)
# - Actions: encode, predict, log_prob
MODEL_FAMILY = ModelFamily(
    base_model_slug=ESMCParams.base_model_slug,
    display_name=ESMCParams.display_name,
    # The @biolm_model_class container class in app.py (used for gateway routing).
    modal_class_name="ESMCModel",
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
            request_schema=ESMCEncodeRequest,
            response_schema=ESMCEncodeResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.PREDICT,
            request_schema=ESMCPredictRequest,
            response_schema=ESMCPredictResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.LOG_PROB,
            request_schema=ESMCPredictLogProbRequest,
            response_schema=ESMCPredictLogProbResponse,
        ),
    ],
    # Single axis: MODEL_SIZE — 300m only (600m excluded, non-commercial license)
    variant_axes={
        "MODEL_SIZE": list(ESMCModelSizes),
    },
    # Resource function looks up the correct spec from the schema
    resource_function=lambda cfg: ESMC_VARIANT_RESOURCE_SPECS[
        ESMCModelSizes(cfg["MODEL_SIZE"])
    ],
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Multi-variant: both return "esmc-{variant}"
    naming_function=lambda base_slug, cfg: (
        f"{base_slug}-{cfg['MODEL_SIZE']}" if cfg else base_slug,
        f"{base_slug}-{cfg['MODEL_SIZE']}" if cfg else base_slug,
    ),
)
