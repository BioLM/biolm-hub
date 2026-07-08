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
from models.progen2.schema import (
    ProGen2GenerateRequest,
    ProGen2GenerateResponse,
    ProGen2ModelTypes,
    ProGen2Params,
)

# Resource Spec
PROGEN2_VARIANT_RESOURCE_SPECS = {
    ProGen2ModelTypes.OAS: ModalResourceSpec(
        cpu=2.0, memory=8 * 1024, gpu=None  # 8GB RAM
    ),
    ProGen2ModelTypes.MEDIUM: ModalResourceSpec(
        cpu=2.0, memory=8 * 1024, gpu=ModalGPU.T4  # 8GB RAM
    ),
    ProGen2ModelTypes.LARGE: ModalResourceSpec(
        cpu=4.0, memory=16 * 1024, gpu=ModalGPU.T4  # 16GB RAM
    ),
    ProGen2ModelTypes.BFD90: ModalResourceSpec(
        cpu=4.0, memory=16 * 1024, gpu=ModalGPU.T4  # 16GB RAM
    ),
}


# ProGen2 configuration:
# - Axes: MODEL_TYPE (oas, medium, large, bfd90)
# - Actions: generate
MODEL_FAMILY = ModelFamily(
    base_model_slug=ProGen2Params.base_model_slug,
    display_name=ProGen2Params.display_name,
    # The @biolm_model_class container class in app.py drives gateway routing.
    modal_class_name="ProGen2Model",
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE],
        input_molecule=[InputMolecule.PROTEIN],
        task=[Task.SEQUENCE_GENERATION],
        output_modality=[OutputModality.SEQUENCE],
        architecture=[Architecture.TRANSFORMER, Architecture.AUTOREGRESSIVE],
    ),
    # Single action: generate
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.GENERATE,
            request_schema=ProGen2GenerateRequest,
            response_schema=ProGen2GenerateResponse,
        )
    ],
    # Single axis: MODEL_TYPE with values oas, medium, large, bfd90
    variant_axes={
        "MODEL_TYPE": list(ProGen2ModelTypes),
    },
    # Resource function looks up the correct spec from the schema
    resource_function=lambda cfg: PROGEN2_VARIANT_RESOURCE_SPECS[
        ProGen2ModelTypes(cfg["MODEL_TYPE"])
    ],
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Multi-variant: both return "progen2-{variant}"
    naming_function=lambda base_slug, cfg: (
        f"{base_slug}-{cfg['MODEL_TYPE']}" if cfg else base_slug,
        f"{base_slug}-{cfg['MODEL_TYPE']}" if cfg else base_slug,
    ),
)
