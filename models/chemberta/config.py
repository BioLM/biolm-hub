from models.chemberta.schema import (
    ChemBERTaEncodeRequest,
    ChemBERTaEncodeResponse,
    ChemBERTaLogProbRequest,
    ChemBERTaLogProbResponse,
    ChemBERTaParams,
)
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

### Static configuration values
# Pinned to a 40-char commit SHA for reproducibility (never "main").
hf_repo_id = "DeepChem/ChemBERTa-100M-MLM"
hf_pin_revision = (
    "f5c45f44d3061f0346888f5c09db17ec1146d29d"  # ChemBERTa HuggingFace pin
)


### ChemBERTa Modal Resource Specs

# CPU-only: ChemBERTa-100M-MLM is a ~92M-parameter RoBERTa (~369 MB on disk).
# A GPU is not worth it for a model this small; CPU inference is fast for the
# short SMILES strings this model consumes (mirrors the esm2 8m/35m CPU tier).
ChemBERTaResourceSpec = ModalResourceSpec(
    cpu=2.0,
    memory=8 * 1024,  # 8 GB RAM
    gpu=None,
)


# ChemBERTa configuration:
# - Axes: None (single variant)
# - Actions: encode, log_prob
MODEL_FAMILY = ModelFamily(
    base_model_slug=ChemBERTaParams.base_model_slug,
    display_name=ChemBERTaParams.display_name,
    # The @biolm_model_class container class in app.py drives gateway routing.
    modal_class_name="ChemBERTaModel",
    tags=ModelTags(
        input_modality=[InputModality.SMILES],
        input_molecule=[InputMolecule.LIGAND],
        task=[Task.EMBEDDING, Task.PROPERTY_PREDICTION],
        output_modality=[
            OutputModality.EMBEDDING,
            OutputModality.LOG_PROBABILITIES,
        ],
        architecture=[Architecture.TRANSFORMER, Architecture.BERT],
    ),
    # Two actions: encode and log_prob
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.ENCODE,
            request_schema=ChemBERTaEncodeRequest,
            response_schema=ChemBERTaEncodeResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.LOG_PROB,
            request_schema=ChemBERTaLogProbRequest,
            response_schema=ChemBERTaLogProbResponse,
        ),
    ],
    # No variants - single model
    variant_axes={},
    # Single resource spec for the only variant
    resource_function=lambda cfg: ChemBERTaResourceSpec,
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Single variant: both return "chemberta"
    naming_function=lambda base_slug, cfg: (base_slug, base_slug),
)
