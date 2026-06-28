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
from models.igt5.schema import (
    IgT5EncodeRequest,
    IgT5EncodeResponse,
    IgT5ModelTypes,
    IgT5Params,
)

### Static configuration values

model_id_mapping = {
    IgT5ModelTypes.UNPAIRED: "IgT5_unpaired",
    IgT5ModelTypes.PAIRED: "IgT5",
}


### IgT5 Modal Resource Specs

IgT5_VARIANT_RESOURCE_SPECS = {
    IgT5ModelTypes.PAIRED: ModalResourceSpec(
        cpu=4.0, memory=16 * 1024, gpu=ModalGPU.T4  # 16GB RAM
    ),
    IgT5ModelTypes.UNPAIRED: ModalResourceSpec(
        cpu=4.0, memory=16 * 1024, gpu=ModalGPU.T4  # 16GB RAM
    ),
}


# IgT5 configuration:
# - Axes: MODEL_TYPE (paired, unpaired)
# - Actions: encode
MODEL_FAMILY = ModelFamily(
    base_model_slug=IgT5Params.base_model_slug,
    display_name=IgT5Params.display_name,
    # The @biolm_model_class container class in app.py (gateway routing, W8).
    modal_class_name="IgT5Model",
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE],
        input_molecule=[InputMolecule.ANTIBODY],
        task=[Task.EMBEDDING],
        output_modality=[OutputModality.EMBEDDING],
        architecture=[Architecture.TRANSFORMER, Architecture.T5],
    ),
    # Single action: encode
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.ENCODE,
            request_schema=IgT5EncodeRequest,
            response_schema=IgT5EncodeResponse,
        )
    ],
    # Single axis: MODEL_TYPE with values paired, unpaired
    variant_axes={
        "MODEL_TYPE": list(IgT5ModelTypes),
    },
    # Resource function looks up the correct spec from the schema
    resource_function=lambda cfg: IgT5_VARIANT_RESOURCE_SPECS[
        IgT5ModelTypes(cfg["MODEL_TYPE"])
    ],
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Multi-variant: both return "igt5-paired", "igt5-unpaired"
    naming_function=lambda base_slug, cfg: (
        f"{base_slug}-{cfg['MODEL_TYPE']}" if cfg else base_slug,
        f"{base_slug}-{cfg['MODEL_TYPE']}" if cfg else base_slug,
    ),
)
