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
from models.msa_transformer.schema import (
    MSATransformerEncodeRequest,
    MSATransformerEncodeResponse,
    MSATransformerParams,
)

# MSA Transformer resource specification
# 100M parameters, but MSA inputs can be large (M sequences × L positions)
MSATransformerResourceSpec = ModalResourceSpec(
    cpu=4.0,
    memory=16 * 1024,  # 16GB RAM
    gpu=ModalGPU.T4,  # 16GB VRAM
    timeout=20 * 60,  # 20 minutes
)

# MSA Transformer configuration:
# - Axes: None (single variant)
# - Actions: encode
MODEL_FAMILY = ModelFamily(
    base_model_slug=MSATransformerParams.base_model_slug,
    display_name=MSATransformerParams.display_name,
    # The @biolm_model_class container class in app.py.
    modal_class_name="MSATransformerModel",
    tags=ModelTags(
        input_modality=[InputModality.MSA],
        input_molecule=[InputMolecule.PROTEIN],
        task=[Task.EMBEDDING],
        output_modality=[OutputModality.EMBEDDING],
        architecture=[Architecture.TRANSFORMER],
    ),
    # Single action: encode
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.ENCODE,
            request_schema=MSATransformerEncodeRequest,
            response_schema=MSATransformerEncodeResponse,
        )
    ],
    # No variants - single deployment
    variant_axes={},
    # Static resource function for single variant
    resource_function=lambda cfg: MSATransformerResourceSpec,
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Single variant: both return base slug
    naming_function=lambda base_slug, cfg: (base_slug, base_slug),
)
