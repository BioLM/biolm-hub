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
from models.spurs.schema import (
    SpursParams,
    SpursPredictRequest,
    SpursPredictResponse,
)

### Static configuration values
SPURS_REPO_URL = "https://github.com/luo-group/SPURS.git"
SPURS_COMMIT = "2bae5fed7dad01fcd4e3962fcd6b30e6930d60f7"

# HuggingFace repository configuration
HF_REPO_ID = "cyclization9/SPURS"
# Deterministic HF snapshot revision used for SPURS weights
HF_REVISION = "ac6e391bccc373f949af6a142282c7569b98c984"


### SPURS Modal Resource Specs

SpursResourceSpec = ModalResourceSpec(
    cpu=4.0,
    memory=16 * 1024,
    gpu=ModalGPU.T4,
)


# SPURS configuration:
# - No axes: single variant model
# - Actions: predict (ΔΔG prediction)
MODEL_FAMILY = ModelFamily(
    base_model_slug=SpursParams.base_model_slug,
    modal_class_name="SpursModel",
    display_name=SpursParams.display_name,
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE, InputModality.STRUCTURE],
        input_molecule=[InputMolecule.PROTEIN],
        task=[Task.PROPERTY_PREDICTION, Task.STABILITY_PREDICTION],
        output_modality=[OutputModality.SCALAR],
        architecture=[Architecture.TRANSFORMER, Architecture.GNN],
    ),
    # Single action: predict (ΔΔG prediction)
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.PREDICT,
            request_schema=SpursPredictRequest,
            response_schema=SpursPredictResponse,
        ),
    ],
    # No variant axes: single variant model
    variant_axes={},
    # Resource function returns the single resource spec
    resource_function=lambda cfg: SpursResourceSpec,
)
