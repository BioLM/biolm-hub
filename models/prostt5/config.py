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
from models.prostt5.schema import (
    ProstT5Directions,
    ProstT5EncodeRequestAA,
    ProstT5EncodeResponse,
    ProstT5GenerateRequestAA,
    ProstT5GenerateResponse,
    ProstT5Params,
    ProstT5Types,
)

### Static configuration values

# HuggingFace source for ProstT5 (all variants share the same weights).
# Revision pinned to a specific commit hash for reproducibility.
PROSTT5_HF_REPO_ID = "Rostlab/ProstT5"
PROSTT5_HF_REVISION = "d7d097d5bf9a993ab8f68488b4681d6ca70db9e5"


### ProstT5 Modal Resource Specs

PROSTT5_VARIANT_RESOURCE_SPECS = {
    ProstT5Types.ENCODE: ModalResourceSpec(
        cpu=4.0,
        memory=16 * 1024,  # 16GB RAM
        gpu=ModalGPU.L4,
    ),
    ProstT5Types.GENERATE: ModalResourceSpec(
        cpu=4.0,
        memory=16 * 1024,  # 16GB RAM
        gpu=ModalGPU.L4,
    ),
}

# ProstT5 configuration:
# - Axes: MODEL_ACTION (encode, generate), MODEL_DIRECTION (fold2AA, AA2fold)
# - Actions: encode, generate
MODEL_FAMILY = ModelFamily(
    base_model_slug=ProstT5Params.base_model_slug,
    display_name=ProstT5Params.display_name,
    modal_class_name="ProstT5Model",
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE],
        input_molecule=[InputMolecule.PROTEIN],
        task=[Task.EMBEDDING, Task.SEQUENCE_GENERATION],
        output_modality=[OutputModality.EMBEDDING, OutputModality.SEQUENCE],
        architecture=[Architecture.TRANSFORMER, Architecture.T5],
    ),
    # Two actions: encode and generate.
    # Each action has two direction-specific request schemas (AA2fold and fold2AA);
    # the AA schema is listed here as the representative for docs/registry purposes.
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.ENCODE,
            request_schema=ProstT5EncodeRequestAA,
            response_schema=ProstT5EncodeResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.GENERATE,
            request_schema=ProstT5GenerateRequestAA,
            response_schema=ProstT5GenerateResponse,
        ),
    ],
    # Two axes: MODEL_ACTION (encode/generate) and MODEL_DIRECTION (fold2AA/AA2fold)
    variant_axes={
        "MODEL_ACTION": list(ProstT5Types),
        "MODEL_DIRECTION": list(ProstT5Directions),
    },
    # Resource function based on action type only
    resource_function=lambda cfg: PROSTT5_VARIANT_RESOURCE_SPECS[
        ProstT5Types(cfg["MODEL_ACTION"])
    ],
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Multi-variant: both return "prostt5-fold2aa-encode", "prostt5-fold2aa-generate", etc.
    naming_function=lambda base_slug, cfg: (
        f"{base_slug}-{cfg['MODEL_DIRECTION'].lower()}-{cfg['MODEL_ACTION']}",
        f"{base_slug}-{cfg['MODEL_DIRECTION'].lower()}-{cfg['MODEL_ACTION']}",
    ),
)
