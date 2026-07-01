from typing import Optional

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
from models.evo.schema import (
    EvoGenerateRequest,
    EvoGenerateResponse,
    EvoLogProbRequest,
    EvoLogProbResponse,
    EvoModelVariants,
    EvoParams,
)

### Evo Modal Resource Specs

EVO_VARIANT_RESOURCE_SPECS = {
    EvoModelVariants.EVO_1_5_8K_BASE: ModalResourceSpec(
        cpu=4.0,
        memory=8 * 1024,  # 8GB
        gpu=ModalGPU.L4,
    ),
    # EvoModelVariants.EVO_1_8K_BASE: ModalResourceSpec(
    #     cpu=4.0,
    #     memory=8 * 1024,
    #     gpu=ModalGPU.L4,
    # ),
    # EvoModelVariants.EVO_1_131K_BASE: ModalResourceSpec(
    #     cpu=4.0,
    #     memory=8 * 1024,
    #     gpu=ModalGPU.L4,
    # ),
    # EvoModelVariants.EVO_1_8K_CRISPR: ModalResourceSpec(
    #     cpu=4.0,
    #     memory=8 * 1024,
    #     gpu=ModalGPU.L4,
    # ),
    # EvoModelVariants.EVO_1_8K_TRANSPOSON: ModalResourceSpec(
    #     cpu=4.0,
    #     memory=8 * 1024,
    #     gpu=ModalGPU.L4,
    # ),
}


def get_build_gpu(variant: str) -> Optional[ModalGPU]:
    """Get the GPU for building the image (used in pip_install gpu=)."""
    return EVO_VARIANT_RESOURCE_SPECS[EvoModelVariants(variant)].gpu


# Map each internal variant enum → the official "Evo" library string
EVO_VARIANT_TO_MODEL_NAME = {
    EvoModelVariants.EVO_1_5_8K_BASE: "evo-1.5-8k-base",
    # EvoModelVariants.EVO_1_8K_BASE: "evo-1-8k-base",
    # EvoModelVariants.EVO_1_131K_BASE: "evo-1-131k-base",
    # EvoModelVariants.EVO_1_8K_CRISPR: "evo-1-8k-crispr",
    # EvoModelVariants.EVO_1_8K_TRANSPOSON: "evo-1-8k-transposon",
}

# Evo configuration:
# - Axes: MODEL_VARIANT (currently only one variant enabled)
# - Actions: log_prob, generate
MODEL_FAMILY = ModelFamily(
    base_model_slug=EvoParams.base_model_slug,
    modal_class_name="EvoModel",
    display_name=EvoParams.display_name,
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE],
        input_molecule=[InputMolecule.DNA],
        task=[Task.SEQUENCE_GENERATION, Task.PROPERTY_PREDICTION],
        output_modality=[OutputModality.SEQUENCE, OutputModality.LOG_PROBABILITIES],
        architecture=[Architecture.TRANSFORMER, Architecture.AUTOREGRESSIVE],
    ),
    # Two actions: log_prob and generate
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.LOG_PROB,
            request_schema=EvoLogProbRequest,
            response_schema=EvoLogProbResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.GENERATE,
            request_schema=EvoGenerateRequest,
            response_schema=EvoGenerateResponse,
        ),
    ],
    # Variant axes - currently only one variant enabled, but can be expanded
    variant_axes={
        "MODEL_VARIANT": [
            EvoModelVariants.EVO_1_5_8K_BASE,
            # Future variants can be uncommented:
            # EvoModelVariants.EVO_1_8K_BASE,
            # EvoModelVariants.EVO_1_131K_BASE,
            # EvoModelVariants.EVO_1_8K_CRISPR,
            # EvoModelVariants.EVO_1_8K_TRANSPOSON,
        ]
    },
    # Resource spec based on variant
    resource_function=lambda cfg: EVO_VARIANT_RESOURCE_SPECS[
        EvoModelVariants(cfg["MODEL_VARIANT"])
    ],
    # Naming function: returns (modal_app_name, public_api_slug)
    naming_function=lambda base_slug, cfg: (
        f"{base_slug}-{cfg['MODEL_VARIANT'].lower()}",
        f"{base_slug}-{cfg['MODEL_VARIANT'].lower()}",
    ),
)
