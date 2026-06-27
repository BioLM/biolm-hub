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

### ESM1v Modal Resource Specs

ESM1v_VARIANT_RESOURCE_SPECS = {
    ESM1vModelNumbers.N1: ModalResourceSpec(
        cpu=2.0, memory=8 * 1024, gpu=None  # 2GB RAM
    ),
    ESM1vModelNumbers.N2: ModalResourceSpec(
        cpu=2.0, memory=8 * 1024, gpu=None  # 2GB RAM
    ),
    ESM1vModelNumbers.N3: ModalResourceSpec(
        cpu=2.0, memory=8 * 1024, gpu=None  # 2GB RAM
    ),
    ESM1vModelNumbers.N4: ModalResourceSpec(
        cpu=2.0, memory=8 * 1024, gpu=None  # 2GB RAM
    ),
    ESM1vModelNumbers.N5: ModalResourceSpec(
        cpu=2.0, memory=8 * 1024, gpu=None  # 2GB RAM
    ),
    ESM1vModelNumbers.ALL: ModalResourceSpec(
        cpu=4.0, memory=28 * 1024, gpu=ModalGPU.T4  # 16GB RAM
    ),
}

# ESM1v configuration:
# - Axes: MODEL_NUMBER (n1, n2, n3, n4, n5, all)
# - Actions: predict
MODEL_FAMILY = ModelFamily(
    base_model_slug=ESM1vParams.base_model_slug,
    display_name=ESM1vParams.display_name,
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
