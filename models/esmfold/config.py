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
from models.esmfold.schema import (
    ESMFoldParams,
    ESMFoldPredictRequest,
    ESMFoldPredictResponse,
)

### ESMFold Modal Resource Specs

ESMFoldResourceSpec = ModalResourceSpec(
    cpu=4.0,
    memory=16 * 1024,  # 16GB RAM
    gpu=ModalGPU.A10G,
)

# ESMFold configuration:
# - Axes: None (single variant)
# - Actions: fold
MODEL_FAMILY = ModelFamily(
    base_model_slug=ESMFoldParams.base_model_slug,
    display_name=ESMFoldParams.display_name,
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE],
        input_molecule=[InputMolecule.PROTEIN, InputMolecule.COMPLEX],
        task=[Task.STRUCTURE_PREDICTION],
        output_modality=[OutputModality.STRUCTURE, OutputModality.SCALAR],
        architecture=[Architecture.TRANSFORMER, Architecture.GNN],
    ),
    # Single action: fold
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.FOLD,
            request_schema=ESMFoldPredictRequest,
            response_schema=ESMFoldPredictResponse,
        )
    ],
    # No variant axes - single model configuration
    variant_axes={},
    # Resource function for single variant
    resource_function=lambda cfg: ESMFoldResourceSpec,
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Single variant: both return "esmfold"
    naming_function=lambda base_slug, cfg: (base_slug, base_slug),
)
