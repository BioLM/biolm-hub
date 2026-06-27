from models.chai1.schema import (
    Chai1Params,
    Chai1PredictRequest,
    Chai1PredictResponse,
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

### Chai-1 Modal Resource Specs

Chai1ResourceSpec = ModalResourceSpec(
    cpu=8.0,
    memory=64 * 1024,  # 64GB
    gpu=ModalGPU.A100_80GB,
)

# Chai1 configuration:
# - Axes: None (single variant)
# - Actions: predict
MODEL_FAMILY = ModelFamily(
    base_model_slug=Chai1Params.base_model_slug,
    display_name=Chai1Params.display_name,
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
        task=[Task.STRUCTURE_PREDICTION],
        output_modality=[OutputModality.STRUCTURE],
        architecture=[Architecture.DIFFUSION, Architecture.TRANSFORMER],
    ),
    # Single action: predict
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.PREDICT,
            request_schema=Chai1PredictRequest,
            response_schema=Chai1PredictResponse,
        )
    ],
    # No variant axes - single variant model
    variant_axes={},
    # Resource function for single variant
    resource_function=lambda cfg: Chai1ResourceSpec,
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Single variant: both return "chai1"
    naming_function=lambda base_slug, cfg: (base_slug, base_slug),
)
