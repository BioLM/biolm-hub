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
from models.dna_chisel.schema import (
    DnaChiselParams,
    DnaChiselPredictRequest,
    DnaChiselPredictResponse,
)

### DNA-Chisel Modal Resource Specs

DnaChiselResourceSpec = ModalResourceSpec(
    cpu=0.25,
    memory=1 * 1024,  # 1 GB
    gpu=None,
)


# DnaChisel configuration:
# - Axes: None (single variant)
# - Actions: encode
MODEL_FAMILY = ModelFamily(
    base_model_slug=DnaChiselParams.base_model_slug,
    display_name=DnaChiselParams.display_name,
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE],
        input_molecule=[InputMolecule.DNA],
        task=[Task.SEQUENCE_OPTIMIZATION, Task.FEATURE_EXTRACTION],
        output_modality=[OutputModality.SCALAR, OutputModality.DICTIONARY],
        architecture=[Architecture.ALGORITHMIC],
    ),
    # Single action: encode (note: action name is encode, not predict)
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.ENCODE,
            request_schema=DnaChiselPredictRequest,
            response_schema=DnaChiselPredictResponse,
        )
    ],
    # No variant axes - single variant model
    variant_axes={},
    # Resource function for single variant
    resource_function=lambda cfg: DnaChiselResourceSpec,
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Single variant: both return "dna-chisel"
    naming_function=lambda base_slug, cfg: (base_slug, base_slug),
)
