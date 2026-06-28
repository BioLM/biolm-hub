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
from models.immunefold.schema import (
    ImmuneFoldModelTypes,
    ImmuneFoldParams,
    ImmuneFoldPredictRequest,
    ImmuneFoldPredictResponse,
)

# Static configuration values
immunefold_commit_hash = (
    "b6d916fc223db2d5e11ea3962894f1b38b07e7b7"  # ImmuneFold GitHub commit
)


### ImmuneFold Modal Resource Specs

ImmuneFold_VARIANT_RESOURCE_SPECS = {
    ImmuneFoldModelTypes.ANTIBODY: ModalResourceSpec(
        cpu=3.0, memory=16 * 1024, gpu=ModalGPU.T4  # ImmuneFold peaks around 15GB
    ),
    ImmuneFoldModelTypes.TCR: ModalResourceSpec(
        cpu=3.0, memory=16 * 1024, gpu=ModalGPU.T4  # ImmuneFold peaks around 15GB
    ),
}


### ImmuneFold Model Configuration Mappings

model_id_mapping = {
    ImmuneFoldModelTypes.ANTIBODY: "immunefold-ab.ckpt",
    ImmuneFoldModelTypes.TCR: "immunefold-tcr.ckpt",
}

model_config_mapping = {
    ImmuneFoldModelTypes.ANTIBODY: "antibody_structure_prediction.yaml",
    ImmuneFoldModelTypes.TCR: "TCR_structure_prediction.yaml",
}

# ImmuneFold configuration:
# - Axes: MODEL_TYPE (antibody, tcr)
# - Actions: fold
MODEL_FAMILY = ModelFamily(
    base_model_slug=ImmuneFoldParams.base_model_slug,
    display_name=ImmuneFoldParams.display_name,
    # The @biolm_model_class container class in app.py (gateway routing, W8).
    modal_class_name="ImmuneFoldModel",
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE, InputModality.STRUCTURE],
        input_molecule=[
            InputMolecule.ANTIBODY,
            InputMolecule.TCR,
            InputMolecule.COMPLEX,
        ],
        task=[Task.STRUCTURE_PREDICTION],
        output_modality=[OutputModality.STRUCTURE, OutputModality.SCALAR],
        architecture=[Architecture.TRANSFORMER, Architecture.GNN],
    ),
    # Single action: fold
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.FOLD,
            request_schema=ImmuneFoldPredictRequest,
            response_schema=ImmuneFoldPredictResponse,
        )
    ],
    # Single axis: MODEL_TYPE with values antibody, tcr
    variant_axes={
        "MODEL_TYPE": list(ImmuneFoldModelTypes),
    },
    # Resource function looks up the correct spec from the schema
    resource_function=lambda cfg: ImmuneFold_VARIANT_RESOURCE_SPECS[
        ImmuneFoldModelTypes(cfg["MODEL_TYPE"])
    ],
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Multi-variant: both return "immunefold-antibody", "immunefold-tcr"
    naming_function=lambda base_slug, cfg: (
        f"{base_slug}-{cfg['MODEL_TYPE']}" if cfg else base_slug,
        f"{base_slug}-{cfg['MODEL_TYPE']}" if cfg else base_slug,
    ),
)
