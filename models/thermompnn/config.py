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
from models.thermompnn.schema import (
    ThermoMPNNParams,
    ThermoMPNNPredictRequest,
    ThermoMPNNPredictResponse,
)

### Static configuration values
thermompnn_commit_hash = "11a1c5b4624f4c60b42fdba4bcaecd3bcb670615"  # Pinned commit

### ThermoMPNN Modal Resource Specs

ThermoMPNNResourceSpec = ModalResourceSpec(
    cpu=2.0,
    memory=8 * 1024,  # 8GB RAM
    gpu=ModalGPU.T4,
)

### ThermoMPNN Model Checkpoints

THERMOMPNN_MODEL_CHECKPOINT = "thermoMPNN_default.pt"

# ThermoMPNN configuration:
# - Single variant (no axes)
# - Actions: predict
MODEL_FAMILY = ModelFamily(
    base_model_slug=ThermoMPNNParams.base_model_slug,
    modal_class_name="ThermoMPNNModel",
    display_name=ThermoMPNNParams.display_name,
    tags=ModelTags(
        input_modality=[InputModality.STRUCTURE],
        input_molecule=[InputMolecule.PROTEIN],
        task=[Task.STABILITY_PREDICTION],
        output_modality=[OutputModality.SCALAR],
        architecture=[Architecture.GNN],
    ),
    # Single action: predict
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.PREDICT,
            request_schema=ThermoMPNNPredictRequest,
            response_schema=ThermoMPNNPredictResponse,
        )
    ],
    # No variant axes - single model
    variant_axes={},
    # Resource function
    resource_function=lambda cfg: ThermoMPNNResourceSpec,
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    naming_function=lambda base_slug, cfg: (
        base_slug,  # modal app: thermompnn
        base_slug,  # public slug: thermompnn
    ),
)
