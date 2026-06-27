from models.biotite.schema import (
    BiotiteExtractChainsRequest,
    BiotiteExtractChainsResponse,
    BiotiteParams,
    BiotiteRMSDRequest,
    BiotiteRMSDResponse,
)
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

### Biotite Modal Resource Specs

BiotiteResourceSpec = ModalResourceSpec(
    cpu=2.0,
    memory=8 * 1024,
    gpu=None,
)


# Biotite configuration:
# - Axes: None (single variant)
# - Actions: generate (extract chains), predict (compute RMSD)
MODEL_FAMILY = ModelFamily(
    base_model_slug=BiotiteParams.base_model_slug,
    modal_class_name="BiotiteModel",
    display_name=BiotiteParams.display_name,
    tags=ModelTags(
        input_modality=[InputModality.STRUCTURE],
        input_molecule=[InputMolecule.PROTEIN, InputMolecule.COMPLEX],
        task=[Task.UTILITY, Task.FEATURE_EXTRACTION],
        output_modality=[
            OutputModality.SEQUENCE,
            OutputModality.STRUCTURE,
            OutputModality.SCALAR,
        ],
        architecture=[Architecture.ALGORITHMIC],
    ),
    # Two actions: generate (extract chains) and predict (compute RMSD)
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.GENERATE,
            request_schema=BiotiteExtractChainsRequest,
            response_schema=BiotiteExtractChainsResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.PREDICT,
            request_schema=BiotiteRMSDRequest,
            response_schema=BiotiteRMSDResponse,
        ),
    ],
    # No variants - single deployment
    variant_axes={},
    # Static resource function for single variant
    resource_function=lambda cfg: BiotiteResourceSpec,
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Single variant: both return "biotite"
    naming_function=lambda base_slug, cfg: (base_slug, base_slug),
)
