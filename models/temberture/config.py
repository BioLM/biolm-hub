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
from models.temberture.schema import (
    TemBERTureEncodeRequest,
    TemBERTureEncodeResponse,
    TemBERTureModelTypes,
    TemBERTureParams,
    TemBERTurePredictRequest,
    TemBERTurePredictResponse,
)

### Static configuration values
# HuggingFace repository configuration for shared ProtBERT base model
hf_repo_id = "Rostlab/prot_bert_bfd"
hf_pinned_revision = (
    "6c5c8a55a52ff08a664dfd584aa1773f125a0487"  # Latest commit for determinism
)

# GitHub repository configuration for adapter downloads
temberture_github_repo = "ibmm-unibe-ch/TemBERTure"
temberture_github_commit = (
    "3c17a7a2d2a8365b187f5dec4eb1ed5db6d37f41"  # Pin to specific commit
)

### TemBERTure Modal Resource Specs

TEMBERTURE_VARIANT_RESOURCE_SPECS = {
    TemBERTureModelTypes.CLASSIFIER: ModalResourceSpec(
        cpu=4.0, memory=16 * 1024, gpu=ModalGPU.T4
    ),
    TemBERTureModelTypes.REGRESSION: ModalResourceSpec(
        cpu=4.0, memory=16 * 1024, gpu=ModalGPU.T4
    ),
}

# TemBERTure configuration:
# - Axes: MODEL_TYPE (classifier, regression)
# - Actions: encode, predict
MODEL_FAMILY = ModelFamily(
    base_model_slug=TemBERTureParams.base_model_slug,
    modal_class_name="TemBERTureModel",
    display_name=TemBERTureParams.display_name,
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE],
        input_molecule=[InputMolecule.PROTEIN],
        task=[Task.EMBEDDING, Task.SEQUENCE_CLASSIFICATION, Task.PROPERTY_PREDICTION],
        output_modality=[
            OutputModality.EMBEDDING,
            OutputModality.SCALAR,
            OutputModality.CLASS_LABEL,
        ],
        architecture=[Architecture.TRANSFORMER],
    ),
    # Two actions: encode, predict
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.ENCODE,
            request_schema=TemBERTureEncodeRequest,
            response_schema=TemBERTureEncodeResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.PREDICT,
            request_schema=TemBERTurePredictRequest,
            response_schema=TemBERTurePredictResponse,
        ),
    ],
    # Single axis: MODEL_TYPE with values classifier, regression
    variant_axes={
        "MODEL_TYPE": list(TemBERTureModelTypes),
    },
    # Resource function looks up the correct spec from the schema
    resource_function=lambda cfg: TEMBERTURE_VARIANT_RESOURCE_SPECS[
        TemBERTureModelTypes(cfg["MODEL_TYPE"])
    ],
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Multi-variant: both return "temberture-classifier", "temberture-regression"
    naming_function=lambda base_slug, cfg: (
        f"{base_slug}-{cfg['MODEL_TYPE']}" if cfg else base_slug,
        f"{base_slug}-{cfg['MODEL_TYPE']}" if cfg else base_slug,
    ),
)
