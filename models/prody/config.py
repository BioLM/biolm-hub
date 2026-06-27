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
from models.prody.schema import (
    ProDyEncodeRequest,
    ProDyEncodeResponse,
    ProDyParams,
    ProDyPredictRequest,
    ProDyPredictResponse,
)

### ProDy Modal Resource Specs

ProDyResourceSpec = ModalResourceSpec(
    cpu=4.0,
    memory=16 * 1024,
    gpu=None,
)


# ProDy configuration:
# - Axes: None (single variant)
# - Actions: encode (InSty interactions), predict (RMSD)
MODEL_FAMILY = ModelFamily(
    base_model_slug=ProDyParams.base_model_slug,
    display_name=ProDyParams.display_name,
    tags=ModelTags(
        input_modality=[InputModality.STRUCTURE],
        input_molecule=[InputMolecule.PROTEIN, InputMolecule.COMPLEX],
        task=[Task.FEATURE_EXTRACTION, Task.UTILITY],
        output_modality=[OutputModality.DICTIONARY, OutputModality.SCALAR],
        architecture=[Architecture.ALGORITHMIC],
    ),
    # Two actions: encode (InSty interactions) and predict (RMSD)
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.ENCODE,
            request_schema=ProDyEncodeRequest,
            response_schema=ProDyEncodeResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.PREDICT,
            request_schema=ProDyPredictRequest,
            response_schema=ProDyPredictResponse,
        ),
    ],
    # No variants - single deployment
    variant_axes={},
    # Static resource function for single variant
    resource_function=lambda cfg: ProDyResourceSpec,
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Single variant: both return "prody"
    naming_function=lambda base_slug, cfg: (base_slug, base_slug),
)
