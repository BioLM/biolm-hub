from models.boltz.schema import (
    BoltzModelParams,
    BoltzModelVersion,
    BoltzPredictRequest,
    BoltzPredictResponse,
)
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

### Boltz Modal Resource Specs

BOLTZ_VARIANT_RESOURCE_SPECS = {
    BoltzModelVersion.BOLTZ1: ModalResourceSpec(
        cpu=4.0,
        memory=24 * 1024,  # 24GB
        gpu=ModalGPU.A100_40GB,
    ),
    BoltzModelVersion.BOLTZ2: ModalResourceSpec(
        cpu=4.0,
        memory=24 * 1024,  # 24GB
        gpu=ModalGPU.A100_40GB,
    ),
}

# Boltz configuration:
# - Axes: MODEL_VERSION (boltz1, boltz2)
# - Actions: fold
MODEL_FAMILY = ModelFamily(
    base_model_slug=BoltzModelParams.base_model_slug,
    modal_class_name="BoltzModel",
    display_name=BoltzModelParams.display_name,
    tags=ModelTags(
        input_modality=[
            InputModality.SEQUENCE,
            InputModality.SMILES,
            InputModality.MSA,
        ],
        input_molecule=[
            InputMolecule.PROTEIN,
            InputMolecule.DNA,
            InputMolecule.RNA,
            InputMolecule.LIGAND,
            InputMolecule.COMPLEX,
        ],
        task=[Task.STRUCTURE_PREDICTION, Task.PROPERTY_PREDICTION],
        output_modality=[OutputModality.STRUCTURE],
        architecture=[Architecture.DIFFUSION, Architecture.TRANSFORMER],
    ),
    # Single action: fold
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.FOLD,
            request_schema=BoltzPredictRequest,
            response_schema=BoltzPredictResponse,
        )
    ],
    # Single axis: MODEL_VERSION with values boltz1, boltz2
    variant_axes={
        "MODEL_VERSION": [v.value for v in BoltzModelVersion],
    },
    # Resource function looks up the correct spec from the enum
    resource_function=lambda cfg: BOLTZ_VARIANT_RESOURCE_SPECS[
        BoltzModelVersion(cfg["MODEL_VERSION"])
    ],
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # For boltz, MODEL_VERSION already contains full name: "boltz1", "boltz2"
    naming_function=lambda base_slug, cfg: (
        cfg["MODEL_VERSION"],  # Just use "boltz1" or "boltz2" directly
        cfg["MODEL_VERSION"],  # Same for public endpoint
    ),
    # Display naming function for user-facing names
    display_naming_function=lambda display_name, cfg: (
        cfg["MODEL_VERSION"].capitalize()
    ),
)
