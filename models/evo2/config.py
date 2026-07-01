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
from models.evo2.schema import (
    Evo2EncodeRequest,
    Evo2EncodeResponse,
    Evo2GenerateRequest,
    Evo2GenerateResponse,
    Evo2LogProbRequest,
    Evo2LogProbResponse,
    Evo2ModelVariants,
    Evo2Params,
)

### Static configuration values
evo2_github_commit_hash = (
    "67a079496b2a7e3630e519e23bcc007800479a15"  # Evo2 GitHub commit
)

# HuggingFace repo IDs for each variant
EVO2_HF_REPO_MAP = {
    Evo2ModelVariants.EVO2_1B_BASE: "arcinstitute/evo2_1b_base",
    Evo2ModelVariants.EVO2_7B_BASE: "arcinstitute/evo2_7b_base",
    # Evo2ModelVariants.EVO2_7B: "arcinstitute/evo2_7b",
    # Evo2ModelVariants.EVO2_40B_BASE: "arcinstitute/evo2_40b_base",
    # Evo2ModelVariants.EVO2_40B: "arcinstitute/evo2_40b",
}

# Checkpoint filenames on HF
EVO2_FILENAME_MAP = {
    Evo2ModelVariants.EVO2_1B_BASE: "evo2_1b_base.pt",
    Evo2ModelVariants.EVO2_7B_BASE: "evo2_7b_base.pt",
    # Evo2ModelVariants.EVO2_7B: "evo2_7b.pt",
    # Evo2ModelVariants.EVO2_40B_BASE: "evo2_40b_base.pt",  # typically split in parts
    # Evo2ModelVariants.EVO2_40B: "evo2_40b.pt",  # likewise
}


### Evo2 Modal Resource Specs

EVO2_VARIANT_RESOURCE_SPECS = {
    # ~1B param, 8k context
    Evo2ModelVariants.EVO2_1B_BASE: ModalResourceSpec(
        cpu=4,
        memory=16 * 1024,  # 16 GB
        gpu=ModalGPU.L4,
    ),
    # ~7B param, 8k context
    Evo2ModelVariants.EVO2_7B_BASE: ModalResourceSpec(
        cpu=4,
        memory=16 * 1024,  # 16 GB
        gpu=ModalGPU.L4,  # upgrade to A100_40GB if needed
    ),
    # # ~7B param, 1M context
    # Evo2ModelVariants.EVO2_7B: ModalResourceSpec(
    #     cpu=8,
    #     memory=16 * 1024,
    #     gpu=ModalGPU.L4,  # upgrade to A100_40GB if needed
    # ),
    # # ~40B param, 8k context
    # Evo2ModelVariants.EVO2_40B_BASE: ModalResourceSpec(
    #     cpu=8,
    #     memory=32 * 1024,
    #     gpu=ModalGPU.A100_40GB,
    # ),
    # # ~40B param, 1M context
    # Evo2ModelVariants.EVO2_40B: ModalResourceSpec(
    #     cpu=8,
    #     memory=32 * 1024,
    #     gpu=ModalGPU.A100_40GB,
    # ),
}

# HuggingFace revision pins for reproducibility
EVO2_HF_REVISION_MAP = {
    Evo2ModelVariants.EVO2_1B_BASE: "fb7b4083b00804ee7a13fdb00631ca8e4ed1ca6d",
    Evo2ModelVariants.EVO2_7B_BASE: "69e43b323420dcb69d10640155e823ade0455a28",
    # Evo2ModelVariants.EVO2_7B: "7dd460d8b1b9ab9a912dad3a27871773d48d30d3",
    # Evo2ModelVariants.EVO2_40B_BASE: "64a0d62f72cee4fd78e30ccba03625d512e39992",
    # Evo2ModelVariants.EVO2_40B: "3aeb6f26e1c2c3a3e2d10eafabefa9f168df6205",
}


# Static configuration values
def get_build_gpu(variant: str) -> ModalGPU:
    """Get the GPU enum value for building CUDA extensions."""
    gpu = EVO2_VARIANT_RESOURCE_SPECS[Evo2ModelVariants(variant)].gpu
    if gpu is None:
        raise ValueError(
            f"Evo2 variant '{variant}' has no GPU configured in "
            "EVO2_VARIANT_RESOURCE_SPECS; a GPU is required to build CUDA extensions."
        )
    return gpu


# Evo2 configuration:
# - Axes: MODEL_VARIANT (1b-base) [only actively tested variant]
# - Actions: encode, log_prob, generate
MODEL_FAMILY = ModelFamily(
    base_model_slug=Evo2Params.base_model_slug,
    display_name=Evo2Params.display_name,
    # The @biolm_model_class container class in app.py (gateway routing, W8).
    modal_class_name="Evo2Model",
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE],
        input_molecule=[InputMolecule.DNA],
        task=[Task.EMBEDDING, Task.SEQUENCE_GENERATION, Task.PROPERTY_PREDICTION],
        output_modality=[
            OutputModality.EMBEDDING,
            OutputModality.SEQUENCE,
            OutputModality.LOG_PROBABILITIES,
        ],
        architecture=[Architecture.TRANSFORMER, Architecture.AUTOREGRESSIVE],
    ),
    # Three actions: encode, log_prob, and generate
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.ENCODE,
            request_schema=Evo2EncodeRequest,
            response_schema=Evo2EncodeResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.LOG_PROB,
            request_schema=Evo2LogProbRequest,
            response_schema=Evo2LogProbResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.GENERATE,
            request_schema=Evo2GenerateRequest,
            response_schema=Evo2GenerateResponse,
        ),
    ],
    # Single axis: MODEL_VARIANT with available values (only actively tested variants)
    variant_axes={
        "MODEL_VARIANT": [Evo2ModelVariants.EVO2_1B_BASE],  # Only test 1b-base variant
    },
    # Resource function looks up the correct spec from the schema
    resource_function=lambda cfg: EVO2_VARIANT_RESOURCE_SPECS[
        Evo2ModelVariants(cfg["MODEL_VARIANT"])
    ],
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Multi-variant: both return "evo2-{variant}"
    naming_function=lambda base_slug, cfg: (
        f"{base_slug}-{cfg['MODEL_VARIANT']}" if cfg else base_slug,
        f"{base_slug}-{cfg['MODEL_VARIANT']}" if cfg else base_slug,
    ),
)
