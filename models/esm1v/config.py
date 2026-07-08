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
from models.esm1v.schema import (
    ESM1vModelNumbers,
    ESM1vParams,
    ESM1vPredictRequest,
    ESM1vPredictResponse,
)

### Static configuration values

# ESM-1v is a 5-member ensemble. Each member is its own HuggingFace repo.
# The "all" variant loads all five members; n1..n5 load a single member.
# Revisions pinned to specific commit hashes for reproducibility.
ESM1V_MEMBERS = ["n1", "n2", "n3", "n4", "n5"]
ESM1V_HF_REPO_MAP = {
    "n1": "facebook/esm1v_t33_650M_UR90S_1",
    "n2": "facebook/esm1v_t33_650M_UR90S_2",
    "n3": "facebook/esm1v_t33_650M_UR90S_3",
    "n4": "facebook/esm1v_t33_650M_UR90S_4",
    "n5": "facebook/esm1v_t33_650M_UR90S_5",
}
ESM1V_HF_REVISION_MAP = {
    "n1": "8bfdb1892536cc77bd0760b9c25ddced2cd0b4c8",
    "n2": "3c1e9e64480f069b163e456c361bfd80a8bab04c",
    "n3": "0b00fd112e63f6b5e70a9cd8484d4e660312ce70",
    "n4": "443968f644da132d323bbc6321a6d443149fa57b",
    "n5": "fb2e51cb0f605cbad2c4ca3bb784be7bc8e2f4a8",
}


### ESM1v Modal Resource Specs

ESM1v_VARIANT_RESOURCE_SPECS = {
    ESM1vModelNumbers.N1: ModalResourceSpec(
        cpu=2.0, memory=8 * 1024, gpu=None  # 8GB RAM
    ),
    ESM1vModelNumbers.N2: ModalResourceSpec(
        cpu=2.0, memory=8 * 1024, gpu=None  # 8GB RAM
    ),
    ESM1vModelNumbers.N3: ModalResourceSpec(
        cpu=2.0, memory=8 * 1024, gpu=None  # 8GB RAM
    ),
    ESM1vModelNumbers.N4: ModalResourceSpec(
        cpu=2.0, memory=8 * 1024, gpu=None  # 8GB RAM
    ),
    ESM1vModelNumbers.N5: ModalResourceSpec(
        cpu=2.0, memory=8 * 1024, gpu=None  # 8GB RAM
    ),
    ESM1vModelNumbers.ALL: ModalResourceSpec(
        cpu=4.0, memory=28 * 1024, gpu=ModalGPU.T4  # 28GB RAM
    ),
}

# ESM1v configuration:
# - Axes: MODEL_NUMBER (n1, n2, n3, n4, n5, all)
# - Actions: predict
MODEL_FAMILY = ModelFamily(
    base_model_slug=ESM1vParams.base_model_slug,
    display_name=ESM1vParams.display_name,
    # The @biolm_model_class container class in app.py drives gateway routing.
    modal_class_name="ESM1vModel",
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE],
        input_molecule=[InputMolecule.PROTEIN],
        task=[Task.SEQUENCE_COMPLETION, Task.PROPERTY_PREDICTION],
        output_modality=[OutputModality.LOGITS],
        architecture=[Architecture.TRANSFORMER],
    ),
    # Single action: predict
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.PREDICT,
            request_schema=ESM1vPredictRequest,
            response_schema=ESM1vPredictResponse,
        )
    ],
    # Single axis: MODEL_NUMBER with values n1, n2, n3, n4, n5, all
    variant_axes={
        "MODEL_NUMBER": list(ESM1vModelNumbers),
    },
    # Resource function looks up the correct spec from the schema
    resource_function=lambda cfg: ESM1v_VARIANT_RESOURCE_SPECS[
        ESM1vModelNumbers(cfg["MODEL_NUMBER"])
    ],
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Multi-variant: both return "esm1v-{variant}"
    naming_function=lambda base_slug, cfg: (
        f"{base_slug}-{cfg['MODEL_NUMBER']}" if cfg else base_slug,
        f"{base_slug}-{cfg['MODEL_NUMBER']}" if cfg else base_slug,
    ),
)
