"""Configuration for RosettaFold3 (RF3) model.

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
from models.rf3.schema import (
    RF3Params,
    RF3PredictRequest,
    RF3PredictResponse,
)

### RF3 Modal Resource Specs

RF3ResourceSpec = ModalResourceSpec(
    cpu=8.0,
    memory=64 * 1024,  # 64GB
    # Try A100_40GB first - can fall back to A100_80GB if needed
    # With reduced batch sizes, 40GB may be sufficient
    gpu=ModalGPU.A100_40GB,  # RF3 requires substantial GPU memory (40GB may work with optimizations)
)

# RF3 configuration:
# - Axes: None (single variant, though multiple checkpoints exist)
# - Actions: fold
MODEL_FAMILY = ModelFamily(
    base_model_slug=RF3Params.base_model_slug,
    modal_class_name="RF3Model",
    display_name=RF3Params.display_name,
    tags=ModelTags(
        input_modality=[
            InputModality.SEQUENCE,
            InputModality.STRUCTURE,
            InputModality.SMILES,
            InputModality.MSA,
        ],
        input_molecule=[
            InputMolecule.PROTEIN,
            InputMolecule.DNA,
            InputMolecule.RNA,
            InputMolecule.LIGAND,
            InputMolecule.COMPLEX,
        ],
        task=[
            Task.STRUCTURE_PREDICTION,
        ],
        output_modality=[OutputModality.STRUCTURE],
        architecture=[Architecture.TRANSFORMER, Architecture.DIFFUSION],
    ),
    # Single action: fold
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.FOLD,
            request_schema=RF3PredictRequest,
            response_schema=RF3PredictResponse,
        )
    ],
    # No variant axes - single variant model
    # Note: Multiple checkpoints exist (latest, preprint, benchmark)
    # but we'll use latest as default
    variant_axes={},
    # Resource function for single variant
    resource_function=lambda cfg: RF3ResourceSpec,
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Single variant: both return "rf3"
    naming_function=lambda base_slug, cfg: (base_slug, base_slug),
)
