"""Configuration for RFdiffusion3 model.

Based on RosettaCommons/foundry implementation (BSD 3-Clause License).
"""

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
from models.rfd3.schema import (
    RFD3DesignRequest,
    RFD3DesignResponse,
    RFD3Params,
)

### RFD3 Modal Resource Specs

RFD3ResourceSpec = ModalResourceSpec(
    cpu=8.0,
    memory=64 * 1024,  # 64GB
    # Try A100_40GB first - can fall back to A100_80GB if needed
    # With low_memory_mode and reduced batch sizes, 40GB may be sufficient
    gpu=ModalGPU.A100_40GB,  # RFD3 requires substantial GPU memory (40GB may work with optimizations)
)

# RFD3 configuration:
# - Axes: None (single variant)
# - Actions: design
MODEL_FAMILY = ModelFamily(
    base_model_slug=RFD3Params.base_model_slug,
    modal_class_name="RFD3Model",
    display_name=RFD3Params.display_name,
    tags=ModelTags(
        input_modality=[
            InputModality.SEQUENCE,
            InputModality.STRUCTURE,
            InputModality.SMILES,
        ],
        input_molecule=[
            InputMolecule.PROTEIN,
            InputMolecule.DNA,
            InputMolecule.RNA,
            InputMolecule.LIGAND,
            InputMolecule.COMPLEX,
        ],
        task=[
            Task.SEQUENCE_GENERATION,
            Task.STRUCTURE_PREDICTION,
            Task.SEQUENCE_OPTIMIZATION,
        ],
        output_modality=[OutputModality.STRUCTURE],
        architecture=[Architecture.DIFFUSION],
    ),
    # Single action: generate (for structure generation/design)
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.GENERATE,
            request_schema=RFD3DesignRequest,
            response_schema=RFD3DesignResponse,
        )
    ],
    # No variant axes - single variant model
    variant_axes={},
    # Resource function for single variant
    resource_function=lambda cfg: RFD3ResourceSpec,
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Single variant: both return "rfd3"
    naming_function=lambda base_slug, cfg: (base_slug, base_slug),
)
