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
from models.peptides.schema import (
    PeptidesEncodeRequest,
    PeptidesEncodeResponse,
    PeptidesParams,
)

### Peptides Modal Resource Specs

PeptidesResourceSpec = ModalResourceSpec(
    cpu=0.125,
    memory=1024,
    gpu=None,
)


### Peptides Features

PEPTIDES_NUMERIC_FEATURES = [
    "aliphatic_index",
    "boman",
    "charge",
    "descriptors",  # contains all descriptors so do not need physical_descriptors
    "frequencies",
    "hydrophobic_moment",
    "hydrophobicity",
    "instability_index",
    "isoelectric_point",
    "mass_shift",
    "molecular_weight",
    "mz",
    # "structural_class", # may be useful, is the predicted structural class ex: alpha
]


# Vector features (arrays/lists)
PEPTIDES_VECTOR_FEATURES = [
    "hydrophobic_moment_profile",
    "hydrophobicity_profile",
    "linker_preference_profile",
    # "membrane_position_profile",  # may be useful, but may need to be parameterized ex: T, S
]


# Peptides configuration:
# - Axes: None (single variant)
# - Actions: encode
MODEL_FAMILY = ModelFamily(
    base_model_slug=PeptidesParams.base_model_slug,
    display_name=PeptidesParams.display_name,
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE],
        input_molecule=[InputMolecule.PEPTIDE],
        task=[Task.FEATURE_EXTRACTION],
        output_modality=[OutputModality.DICTIONARY],
        architecture=[Architecture.ALGORITHMIC],
    ),
    # Single action: encode
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.ENCODE,
            request_schema=PeptidesEncodeRequest,
            response_schema=PeptidesEncodeResponse,
        )
    ],
    # No variants - single deployment
    variant_axes={},
    # Static resource function for single variant
    resource_function=lambda cfg: PeptidesResourceSpec,
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Single variant: both return "peptides"
    naming_function=lambda base_slug, cfg: (base_slug, base_slug),
)
