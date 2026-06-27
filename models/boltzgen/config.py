from models.boltzgen.schema import (
    BoltzGenDesignRequest,
    BoltzGenDesignResponse,
    BoltzGenParams,
)
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

### BoltzGen Modal Resource Specs

# BoltzGen requires significant GPU memory for the diffusion model
BOLTZGEN_RESOURCE_SPEC = ModalResourceSpec(
    cpu=8.0,
    memory=64 * 1024,  # 64GB RAM
    gpu=ModalGPU.A100_40GB,
    timeout=86400,  # 24 hours (maximum timeout for GPU functions)
)

# BoltzGen configuration:
# - Single variant (no axes)
# - Actions: generate (designs protein variants)
MODEL_FAMILY = ModelFamily(
    base_model_slug=BoltzGenParams.base_model_slug,
    modal_class_name="BoltzGenModel",
    display_name=BoltzGenParams.display_name,
    tags=ModelTags(
        input_modality=[
            InputModality.SEQUENCE,
            InputModality.SMILES,
            InputModality.STRUCTURE,
        ],
        input_molecule=[
            InputMolecule.PROTEIN,
            InputMolecule.DNA,
            InputMolecule.RNA,
            InputMolecule.LIGAND,
            InputMolecule.COMPLEX,
        ],
        task=[Task.SEQUENCE_GENERATION, Task.STRUCTURE_PREDICTION],
        output_modality=[OutputModality.STRUCTURE, OutputModality.SEQUENCE],
        architecture=[Architecture.DIFFUSION, Architecture.TRANSFORMER],
    ),
    # Single action: generate (designs protein variants)
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.GENERATE,
            request_schema=BoltzGenDesignRequest,
            response_schema=BoltzGenDesignResponse,
        )
    ],
    # No variants - single deployment
    variant_axes={},
    # Static resource function for single variant
    resource_function=lambda cfg: BOLTZGEN_RESOURCE_SPEC,
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Single variant: both return "boltzgen"
    naming_function=lambda base_slug, cfg: (base_slug, base_slug),
)
