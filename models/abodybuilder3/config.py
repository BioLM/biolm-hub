from models.abodybuilder3.schema import (
    AbodyBuilder3ModelTypes,
    AbodyBuilder3Params,
    AbodyBuilder3PredictRequest,
    AbodyBuilder3PredictResponse,
)
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

### Static configuration values
abodybuilder3_commit_hash = (
    "18e4058015a39c5405c08a0d5629cf302627b253"  # AbodyBuilder3 GitHub commit
)


### AbodyBuilder3 Modal Resource Specs

ABODYBUILDER3_VARIANT_RESOURCE_SPECS = {
    AbodyBuilder3ModelTypes.PLDDT: ModalResourceSpec(
        cpu=2.0, memory=8 * 1024, gpu=None  # 8GB RAM
    ),
    AbodyBuilder3ModelTypes.LANGUAGE: ModalResourceSpec(
        cpu=4.0, memory=12 * 1024, gpu=ModalGPU.L40S  # 48GB RAM
    ),
}

# AbodyBuilder3 configuration:
# - Axes: MODEL_TYPE (language, plddt)
# - Actions: fold
MODEL_FAMILY = ModelFamily(
    base_model_slug=AbodyBuilder3Params.base_model_slug,
    display_name=AbodyBuilder3Params.display_name,
    # The @biolm_model_class container class in app.py (gateway routing).
    modal_class_name="AbodyBuilder3Model",
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE],
        input_molecule=[InputMolecule.ANTIBODY],
        task=[Task.STRUCTURE_PREDICTION],
        output_modality=[OutputModality.STRUCTURE, OutputModality.SCALAR],
        architecture=[Architecture.GNN],
    ),
    # Single action: fold
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.FOLD,
            request_schema=AbodyBuilder3PredictRequest,
            response_schema=AbodyBuilder3PredictResponse,
        )
    ],
    # Single axis: MODEL_TYPE with values plddt, language
    variant_axes={
        "MODEL_TYPE": list(AbodyBuilder3ModelTypes),
    },
    # Resource function looks up the correct spec from the schema
    resource_function=lambda cfg: ABODYBUILDER3_VARIANT_RESOURCE_SPECS[
        AbodyBuilder3ModelTypes(cfg["MODEL_TYPE"])
    ],
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Multi-variant: both return "abodybuilder3-{variant}"
    naming_function=lambda base_slug, cfg: (
        f"{base_slug}-{cfg['MODEL_TYPE']}" if cfg else base_slug,
        f"{base_slug}-{cfg['MODEL_TYPE']}" if cfg else base_slug,
    ),
)
