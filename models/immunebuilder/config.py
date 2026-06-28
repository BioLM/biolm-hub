from models.commons.model.config import ActionSchemaMap, ModelFamily
from models.commons.model.schema import ModalResourceSpec, ModelActions
from models.commons.model.tag import (
    Architecture,
    InputModality,
    InputMolecule,
    ModelTags,
    OutputModality,
    Task,
)
from models.immunebuilder.schema import (
    ImmuneBuilderModelTypes,
    ImmuneBuilderParams,
    ImmuneBuilderPredictRequest,
    ImmuneBuilderPredictResponse,
)

### ImmuneBuilder Modal Resource Specs

IMMUNE_BUILDER_VARIANT_RESOURCE_SPECS = {
    ImmuneBuilderModelTypes.TCRBUILDER2: ModalResourceSpec(
        cpu=2.0, memory=8 * 1024, gpu=None  # 8GB RAM
    ),
    ImmuneBuilderModelTypes.TCRBUILDER2PLUS: ModalResourceSpec(
        cpu=2.0, memory=8 * 1024, gpu=None  # 8GB RAM
    ),
    ImmuneBuilderModelTypes.ABODYBUILDER2: ModalResourceSpec(
        cpu=2.0, memory=8 * 1024, gpu=None  # 8GB RAM
    ),
    ImmuneBuilderModelTypes.NANOBODYBUILDER2: ModalResourceSpec(
        cpu=2.0, memory=8 * 1024, gpu=None  # 8GB RAM
    ),
}

# ImmuneBuilder configuration:
# - Axes: MODEL_TYPE (tcrbuilder2, tcrbuilder2plus, abodybuilder2, nanobodybuilder2)
# - Actions: fold
MODEL_FAMILY = ModelFamily(
    base_model_slug=ImmuneBuilderParams.base_model_slug,
    display_name=ImmuneBuilderParams.display_name,
    # The @biolm_model_class container class in app.py (gateway routing, W8).
    modal_class_name="ImmuneBuilderModel",
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE],
        input_molecule=[
            InputMolecule.ANTIBODY,
            InputMolecule.NANOBODY,
            InputMolecule.TCR,
        ],
        task=[Task.STRUCTURE_PREDICTION],
        output_modality=[OutputModality.STRUCTURE],
        architecture=[Architecture.GNN],
    ),
    # Single action: fold
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.FOLD,
            request_schema=ImmuneBuilderPredictRequest,
            response_schema=ImmuneBuilderPredictResponse,
        )
    ],
    # Single axis: MODEL_TYPE with 4 values
    variant_axes={
        "MODEL_TYPE": list(ImmuneBuilderModelTypes),
    },
    # Resource function looks up the correct spec from the schema
    resource_function=lambda cfg: IMMUNE_BUILDER_VARIANT_RESOURCE_SPECS[
        ImmuneBuilderModelTypes(cfg["MODEL_TYPE"])
    ],
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Multi-variant: both return "immunebuilder-{variant}"
    naming_function=lambda base_slug, cfg: (
        f"{base_slug}-{cfg['MODEL_TYPE']}" if cfg else base_slug,
        f"{base_slug}-{cfg['MODEL_TYPE']}" if cfg else base_slug,
    ),
)
