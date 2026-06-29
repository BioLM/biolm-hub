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
from models.sadie.schema import (
    SADIEParams,
    SADIEPredictRequest,
    SADIEPredictResponse,
)

### SADIE Modal Resource Specs

SADIEResourceSpec = ModalResourceSpec(
    cpu=0.125,
    memory=1024,  # 1024 MB (1 GB) RAM
    gpu=None,
)


# SADIE configuration:
# - Axes: None (single variant)
# - Actions: predict
MODEL_FAMILY = ModelFamily(
    base_model_slug=SADIEParams.base_model_slug,
    display_name=SADIEParams.display_name,
    # The @biolm_model_class container class in app.py (gateway routing, W8).
    modal_class_name="SADIEModel",
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE],
        input_molecule=[InputMolecule.ANTIBODY, InputMolecule.TCR],
        task=[Task.ANNOTATION],
        output_modality=[OutputModality.ANNOTATIONS],
        architecture=[Architecture.ALGORITHMIC],
    ),
    # Single action: predict
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.PREDICT,
            request_schema=SADIEPredictRequest,
            response_schema=SADIEPredictResponse,
        )
    ],
    # No variants - single deployment
    variant_axes={},
    # Static resource function for single variant
    resource_function=lambda cfg: SADIEResourceSpec,
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Single variant: both return "sadie"
    naming_function=lambda base_slug, cfg: (base_slug, base_slug),
)
