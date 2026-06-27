from models.commons.model.config import ActionSchemaMap, ModelFamily
from models.commons.model.schema import (
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
from models.mpnn.schema import (
    GlobalMembraneMPNNGenerateParams,
    LigandMPNNGenerateParams,
    MPNNGenerateParams,
    MPNNGenerateRequest,
    MPNNGenerateResponse,
    MPNNModelTypes,
    MPNNParams,
    ResidueMembraneMPNNGenerateParams,
)

### Static configuration values
mpnn_commit_hash = (
    "091ab1ff5fb4d13854cf6a7c41ec531e1d9d3e67"  # LigandMPNN GitHub commit
)


### MPNN Modal Resource Specs

MPNNResourceSpec = ModalResourceSpec(
    cpu=1.0,
    memory=3072,  # 3GB RAM
    gpu=None,
)


### MPNN Model Checkpoints and Input Schema Map

MPNNModelCheckpoints = {
    MPNNModelTypes.PROTEIN: "proteinmpnn_v_48_020.pt",
    MPNNModelTypes.LIGAND: "ligandmpnn_v_32_010_25.pt",
    MPNNModelTypes.SOLUBLE: "solublempnn_v_48_020.pt",
    MPNNModelTypes.GLOBAL_LABEL_MEMBRANE: "global_label_membrane_mpnn_v_48_020.pt",
    MPNNModelTypes.PER_RESIDUE_LABEL_MEMBRANE: "per_residue_label_membrane_mpnn_v_48_020.pt",
    MPNNModelTypes.HYPER: "v48_020_epoch300_hyper.pt",
    MPNNModelTypes.SIDE_CHAIN: "ligandmpnn_sc_v_32_002_16.pt",
}

# Map MODEL_TYPE to its specific schema for strict validation
mpnn_schema_map = {
    MPNNModelTypes.PROTEIN: MPNNGenerateParams,
    MPNNModelTypes.LIGAND: LigandMPNNGenerateParams,
    MPNNModelTypes.SOLUBLE: MPNNGenerateParams,
    MPNNModelTypes.GLOBAL_LABEL_MEMBRANE: GlobalMembraneMPNNGenerateParams,
    MPNNModelTypes.PER_RESIDUE_LABEL_MEMBRANE: ResidueMembraneMPNNGenerateParams,
    MPNNModelTypes.HYPER: MPNNGenerateParams,
    MPNNModelTypes.SIDE_CHAIN: MPNNGenerateParams,
}

# MPNN configuration:
# - Axes: MODEL_TYPE (protein, ligand, soluble, global_label_membrane, per_residue_label_membrane, hyper)
# - Actions: generate
MODEL_FAMILY = ModelFamily(
    base_model_slug=MPNNParams.base_model_slug,
    display_name=MPNNParams.display_name,
    tags=ModelTags(
        input_modality=[InputModality.STRUCTURE],
        input_molecule=[InputMolecule.PROTEIN, InputMolecule.COMPLEX],
        task=[Task.INVERSE_FOLDING],
        output_modality=[OutputModality.SEQUENCE],
        architecture=[Architecture.GNN],
    ),
    # Single action: generate
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.GENERATE,
            request_schema=MPNNGenerateRequest,
            response_schema=MPNNGenerateResponse,
        )
    ],
    # Single axis: MODEL_TYPE with 5 values (excluding SIDE_CHAIN)
    variant_axes={
        "MODEL_TYPE": [
            v
            for v in MPNNModelTypes
            if v
            != MPNNModelTypes.SIDE_CHAIN  # We are disabling this for now, can always re-enable
        ],
    },
    # Resource function - all variants use the same resource spec
    resource_function=lambda cfg: MPNNResourceSpec,
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    naming_function=lambda base_slug, cfg: (
        f"{cfg['MODEL_TYPE'].replace('_', '-')}-{base_slug}",  # modal app: protein-mpnn
        f"{cfg['MODEL_TYPE'].replace('_', '-')}-{base_slug}",  # public slug: protein-mpnn
    ),
)
