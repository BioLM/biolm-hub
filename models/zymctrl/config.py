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
from models.zymctrl.schema import (
    ZymCTRLEncodeRequest,
    ZymCTRLEncodeResponse,
    ZymCTRLGenerateRequest,
    ZymCTRLGenerateResponse,
    ZymCTRLParams,
)

### Static configuration values
# HuggingFace repository configuration
HF_REPO_ID = "AI4PD/ZymCTRL"
# Pin specific revision for reproducibility
HF_REVISION = "3c532ef172b9cd2e95238baadf5167ebb89fbc32"


### ZymCTRL Modal Resource Specs
# Single resource spec for ZymCTRL (738M parameter model)
ZYMCTRL_RESOURCE_SPEC = ModalResourceSpec(
    cpu=2.0,
    memory=16 * 1024,  # 16GB RAM
    gpu=ModalGPU.T4,
    timeout=10 * 60,  # 10 minutes
)


# ZymCTRL configuration:
# - Single variant (no size variants)
# - Actions: generate, encode
MODEL_FAMILY = ModelFamily(
    base_model_slug=ZymCTRLParams.base_model_slug,
    display_name=ZymCTRLParams.display_name,
    # The @biolm_model_class container class in app.py (gateway routing, W8).
    modal_class_name="ZymCTRLModel",
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE, InputModality.TEXT],
        input_molecule=[InputMolecule.PROTEIN],
        task=[Task.SEQUENCE_GENERATION, Task.EMBEDDING],
        output_modality=[OutputModality.SEQUENCE, OutputModality.EMBEDDING],
        architecture=[Architecture.TRANSFORMER, Architecture.AUTOREGRESSIVE],
    ),
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.GENERATE,
            request_schema=ZymCTRLGenerateRequest,
            response_schema=ZymCTRLGenerateResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.ENCODE,
            request_schema=ZymCTRLEncodeRequest,
            response_schema=ZymCTRLEncodeResponse,
        ),
    ],
    # Single variant: no axes
    variant_axes={},
    # Always return the same resource spec
    resource_function=lambda cfg: ZYMCTRL_RESOURCE_SPEC,
    # Single variant: app name is just base slug
    naming_function=lambda base_slug, cfg: (base_slug, base_slug),
)
