from models.commons.model.config import ActionSchemaMap, ModelFamily
from models.commons.model.schema import (
    ModalGPU,
    ModalResourceSpec,
    ModelActions,
)
from models.commons.model.tag import (
    Architecture,
    InputModality,
    InputMolecule,
    ModelTags,
    OutputModality,
    Task,
)
from models.pro1.schema import (
    Pro1GenerateRequest,
    Pro1GenerateResponse,
    Pro1Params,
    Pro1Variant,
)

### Static configuration values

# HuggingFace repo ID for all Pro-1 adapters
PRO1_HF_REPO = "mhla/pro-1"

# Pinned HuggingFace revisions (40-char commit SHAs).
# Update these when intentionally upgrading model weights.
# We use the unsloth-pre-quantized 4-bit base model directly so that
# unsloth.FastLanguageModel.from_pretrained does not auto-rewrite the repo
# at load time (which would bypass our cache and the pinned revision).
PRO1_BASE_MODEL_REVISION = "0db785ab56c082e30ae7dea3645d45465fbb5797"
PRO1_ADAPTER_REVISION = "f8f68951ba001326953309da666bc1e1f970866f"

# Map each variant to (base_model_name, adapter_subfolder)
# Subfolders are paths within the mhla/pro-1 HF repo
PRO1_VARIANT_TO_HF_CONFIG = {
    Pro1Variant.SIZE_8B: (
        "unsloth/Meta-Llama-3.1-8B-Instruct-unsloth-bnb-4bit",
        "all-lm-grpo-mega-run/checkpoints/checkpoint-20250225-025056-step40",
    ),
    Pro1Variant.SIZE_8B_GRPO: (
        "unsloth/Meta-Llama-3.1-8B-Instruct-unsloth-bnb-4bit",
        "best-checkpoint",
    ),
}

### Pro-1 Modal Resource Specs

PRO1_8B_RESOURCE_SPEC = ModalResourceSpec(
    cpu=4.0,
    memory=16 * 1024,  # 16 GB RAM
    gpu=ModalGPU.A10G,
)

PRO1_VARIANT_RESOURCE_SPECS = {
    Pro1Variant.SIZE_8B: PRO1_8B_RESOURCE_SPEC,
    Pro1Variant.SIZE_8B_GRPO: PRO1_8B_RESOURCE_SPEC,
}


def get_resource_spec(variant: Pro1Variant) -> ModalResourceSpec:
    return PRO1_VARIANT_RESOURCE_SPECS[variant]


def get_build_gpu(variant: Pro1Variant) -> ModalGPU:
    return PRO1_VARIANT_RESOURCE_SPECS[variant].gpu


# Pro-1 configuration:
# - Axes: MODEL_VARIANT (8b, 8b-grpo)
# - Actions: generate
_DEFAULT_VARIANT = Pro1Variant.SIZE_8B.value

MODEL_FAMILY = ModelFamily(
    base_model_slug=Pro1Params.base_model_slug,
    display_name=Pro1Params.display_name,
    # The @biolm_model_class container class in app.py (gateway routing).
    modal_class_name="Pro1Model",
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE, InputModality.TEXT],
        input_molecule=[InputMolecule.PROTEIN],
        task=[Task.SEQUENCE_OPTIMIZATION],
        output_modality=[OutputModality.SEQUENCE, OutputModality.TEXT],
        architecture=[Architecture.TRANSFORMER, Architecture.AUTOREGRESSIVE],
    ),
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.GENERATE,
            request_schema=Pro1GenerateRequest,
            response_schema=Pro1GenerateResponse,
        )
    ],
    variant_axes={
        "MODEL_VARIANT": [
            Pro1Variant.SIZE_8B,
            Pro1Variant.SIZE_8B_GRPO,
        ]
    },
    resource_function=lambda cfg: get_resource_spec(
        Pro1Variant(cfg.get("MODEL_VARIANT", _DEFAULT_VARIANT))
    ),
    naming_function=lambda base_slug, cfg: (
        f"{base_slug}-{cfg.get('MODEL_VARIANT', _DEFAULT_VARIANT)}",
        f"{base_slug}-{cfg.get('MODEL_VARIANT', _DEFAULT_VARIANT)}",
    ),
)
