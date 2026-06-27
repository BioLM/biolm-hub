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
from models.propermab.schema import (
    ProperMABExtractFeaturesRequest,
    ProperMABExtractFeaturesResponse,
    ProperMABParams,
)

### ProperMAB Modal Resource Specs

# ProperMAB requires significant CPU and memory for:
# - ABodyBuilder2 structure prediction (EGNN model)
# - NanoShaper surface mesh generation
# - APBS Poisson-Boltzmann electrostatics
# - FreeSASA solvent accessibility calculations
# - OpenMM force field calculations
#
# Resource requirements based on implementation guide:
# - CPU: 8 cores (structure prediction + feature extraction are CPU-intensive)
# - Memory: 32GB (APBS and structure prediction need significant RAM)
# - GPU: None (ABodyBuilder2 and all tools are CPU-only)
# - Timeout: 900s (60s per run × 5 max runs + feature extraction overhead)
ProperMABResourceSpec = ModalResourceSpec(
    cpu=8.0,
    memory=32 * 1024,  # 32GB RAM
    gpu=None,  # CPU-only
    timeout=900,  # 15 minutes (60s per run × 5 max runs + overhead)
)


### ProperMAB Configuration

# ProperMAB configuration:
# - Axes: None (single variant)
# - Actions: extract_features
# - Model: Feature engineering framework (not a prediction model)
# - Output: 34 biophysical features (7 sequence + 27 structure)
MODEL_FAMILY = ModelFamily(
    base_model_slug=ProperMABParams.base_model_slug,
    display_name=ProperMABParams.display_name,
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE],
        input_molecule=[InputMolecule.ANTIBODY],
        task=[Task.FEATURE_EXTRACTION],
        output_modality=[OutputModality.DICTIONARY],
        architecture=[
            Architecture.GNN,  # ABodyBuilder2 uses EGNN
            Architecture.ALGORITHMIC,  # Feature extraction algorithms
        ],
    ),
    # Single action: extract_features
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.EXTRACT_FEATURES,
            request_schema=ProperMABExtractFeaturesRequest,
            response_schema=ProperMABExtractFeaturesResponse,
        )
    ],
    # No variants - single deployment
    variant_axes={},
    # Static resource function for single variant
    resource_function=lambda cfg: ProperMABResourceSpec,
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Single variant: both return "propermab"
    naming_function=lambda base_slug, cfg: (base_slug, base_slug),
)
