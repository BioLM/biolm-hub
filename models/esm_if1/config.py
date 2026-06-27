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
from models.esm_if1.schema import (
    ESMIF1GenerateRequest,
    ESMIF1GenerateResponse,
    ESMIF1Params,
)

### ESM-IF1 Modal Resource Specs

ESMIF1ResourceSpec = ModalResourceSpec(
    cpu=4.0,
    memory=16 * 1024,  # 16GB RAM
    gpu=ModalGPU.T4,
)

# ESM-IF1 configuration:
# - Axes: None (single variant)
# - Actions: generate
MODEL_FAMILY = ModelFamily(
    base_model_slug=ESMIF1Params.base_model_slug,
    display_name=ESMIF1Params.display_name,
    # The @biolm_model_class container class in app.py (gateway routing, W8).
    modal_class_name="ESMIF1Model",
    tags=ModelTags(
        input_modality=[InputModality.STRUCTURE],
        input_molecule=[InputMolecule.PROTEIN],
        task=[Task.INVERSE_FOLDING],
        output_modality=[OutputModality.SEQUENCE],
        architecture=[Architecture.GNN, Architecture.AUTOREGRESSIVE],
    ),
    # Single action: generate
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.GENERATE,
            request_schema=ESMIF1GenerateRequest,
            response_schema=ESMIF1GenerateResponse,
        ),
    ],
    # No variants - single model
    variant_axes={},
    # Single resource spec for the only variant
    resource_function=lambda cfg: ESMIF1ResourceSpec,
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Single variant: both return "esm-if1"
    naming_function=lambda base_slug, cfg: (base_slug, base_slug),
)
