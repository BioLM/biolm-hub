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
from models.dsm.schema import (
    DSMEncodeRequest,
    DSMEncodeResponse,
    DSMGenerateRequest,
    DSMGenerateResponse,
    DSMModelSizes,
    DSMParams,
    DSMScoreRequest,
    DSMScoreResponse,
    DSMVariants,
)

# HuggingFace repository mapping for DSM models
DSM_HF_REPO_MAP = {
    (DSMModelSizes.SIZE_150M, DSMVariants.BASE): "GleghornLab/DSM_150",
    (DSMModelSizes.SIZE_650M, DSMVariants.BASE): "GleghornLab/DSM_650",
    (DSMModelSizes.SIZE_650M, DSMVariants.PPI): "Synthyra/DSM_ppi_full",
    # Note: DSM_3B not yet released on HuggingFace
    # (DSMModelSizes.SIZE_3B, DSMVariants.BASE): "GleghornLab/DSM_3B",
}

# Pin specific revisions for reproducibility
DSM_HF_REVISION_MAP = {
    (
        DSMModelSizes.SIZE_150M,
        DSMVariants.BASE,
    ): "47ab75f1ca3a9f3c2d405c7a32943680bee79431",
    (
        DSMModelSizes.SIZE_650M,
        DSMVariants.BASE,
    ): "fbaff3fc21e22cb5b0b85102ebac6c1c642d44dc",
    (
        DSMModelSizes.SIZE_650M,
        DSMVariants.PPI,
    ): "f3ed2e2249a0e102e5aa2a4fdc302bb492e7d6f2",
}


DSM_VARIANT_RESOURCE_SPECS = {
    (DSMModelSizes.SIZE_150M, DSMVariants.BASE): ModalResourceSpec(
        cpu=4.0,
        memory=16 * 1024,  # 16 GB
        gpu=ModalGPU.A10G,
    ),
    (DSMModelSizes.SIZE_650M, DSMVariants.BASE): ModalResourceSpec(
        cpu=8.0,
        memory=32 * 1024,  # 32 GB
        gpu=ModalGPU.A10G,
    ),
    (DSMModelSizes.SIZE_650M, DSMVariants.PPI): ModalResourceSpec(
        cpu=8.0,
        memory=32 * 1024,  # 32 GB
        gpu=ModalGPU.A10G,
    ),
    (DSMModelSizes.SIZE_3B, DSMVariants.BASE): ModalResourceSpec(
        cpu=16.0,
        memory=64 * 1024,  # 64 GB
        gpu=ModalGPU.A100_40GB,
    ),
}


# DSM configuration:
# - Axes: MODEL_SIZE (150m, 650m, 3b) × VARIANT (base, ppi)
# - Actions: predict (generate), encode, score
MODEL_FAMILY = ModelFamily(
    base_model_slug=DSMParams.base_model_slug,
    display_name=DSMParams.display_name,
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE],
        input_molecule=[InputMolecule.PROTEIN],
        task=[
            Task.SEQUENCE_GENERATION,
            Task.EMBEDDING,
            Task.PROPERTY_PREDICTION,
            Task.SEQUENCE_OPTIMIZATION,
        ],
        output_modality=[
            OutputModality.SEQUENCE,
            OutputModality.EMBEDDING,
            OutputModality.LOG_PROBABILITIES,
        ],
        architecture=[Architecture.TRANSFORMER, Architecture.DIFFUSION],
    ),
    # Three actions: generate, encode, score
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.GENERATE,
            request_schema=DSMGenerateRequest,
            response_schema=DSMGenerateResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.ENCODE,
            request_schema=DSMEncodeRequest,
            response_schema=DSMEncodeResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.SCORE,
            request_schema=DSMScoreRequest,
            response_schema=DSMScoreResponse,
        ),
    ],
    # Two axes: MODEL_SIZE and VARIANT
    variant_axes={
        "MODEL_SIZE": list(DSMModelSizes),
        "VARIANT": list(DSMVariants),
    },
    # Resource function looks up the correct spec from the dict
    resource_function=lambda cfg: DSM_VARIANT_RESOURCE_SPECS[
        (DSMModelSizes(cfg["MODEL_SIZE"]), DSMVariants(cfg["VARIANT"]))
    ],
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Multi-variant: both return "dsm-{size}-{variant}"
    naming_function=lambda base_slug, cfg: (
        f"{base_slug}-{cfg['MODEL_SIZE']}-{cfg['VARIANT']}" if cfg else base_slug,
        f"{base_slug}-{cfg['MODEL_SIZE']}-{cfg['VARIANT']}" if cfg else base_slug,
    ),
    # Exclude invalid combinations: PPI is only available for 650M, 3B base not yet released
    excluded_variant_combos=[
        {"MODEL_SIZE": "150m", "VARIANT": "ppi"},
        {"MODEL_SIZE": "3b", "VARIANT": "ppi"},
        # 3B base not yet released on HuggingFace
        {"MODEL_SIZE": "3b", "VARIANT": "base"},
    ],
)
