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
from models.thermompnn_d.schema import (
    ThermoMPNNDParams,
    ThermoMPNNDPredictRequest,
    ThermoMPNNDPredictResponse,
)

### Static configuration values
thermompnn_d_commit_hash = "64a24fea2dfb808c69f667fd741ac96ac54df85b"  # Pinned commit

### ThermoMPNN-D Modal Resource Specs

ThermoMPNNDResourceSpec = ModalResourceSpec(
    cpu=2.0,
    memory=12 * 1024,  # 12GB RAM (loads 2 models)
    gpu=ModalGPU.T4,
)

### ThermoMPNN-D Model Checkpoints

THERMOMPNN_D_EPISTATIC_CHECKPOINT = "ThermoMPNN-D-ens1.ckpt"
THERMOMPNN_SINGLE_CHECKPOINT = "ThermoMPNN-ens1.ckpt"
PROTEIN_MPNN_CHECKPOINT = "v_48_020.pt"  # Base ProteinMPNN model

# ThermoMPNN-D configuration:
# - Single variant (no axes)
# - Actions: predict
MODEL_FAMILY = ModelFamily(
    base_model_slug=ThermoMPNNDParams.base_model_slug,
    modal_class_name="ThermoMPNNDModel",
    display_name=ThermoMPNNDParams.display_name,
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
            request_schema=ThermoMPNNDPredictRequest,
            response_schema=ThermoMPNNDPredictResponse,
        )
    ],
    # No variant axes - single model
    variant_axes={},
    # Resource function
    resource_function=lambda cfg: ThermoMPNNDResourceSpec,
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    naming_function=lambda base_slug, cfg: (
        base_slug,  # modal app: thermompnn-d
        base_slug,  # public slug: thermompnn-d
    ),
)
