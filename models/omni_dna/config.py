from models.commons.model.config import ActionSchemaMap, ModelFamily
from models.commons.model.schema import (
    ModalGPU,
    ModalResourceSpec,
    ModelActions,
)
from models.commons.model.tag import (
    Architecture,
    InputModality,
    InputMolecule,
    ModelTags,
    OutputModality,
    Task,
)
from models.omni_dna.schema import (
    OmniDNAEncodeRequest,
    OmniDNAEncodeResponse,
    OmniDNALogProbRequest,
    OmniDNALogProbResponse,
    OmniDNAModelSizes,
    OmniDNAParams,
)

### Static configuration values
hf_model_name_mapping = {
    # OmniDNAModelSizes.SIZE_20M: "zehui127/Omni-DNA-20M",
    # OmniDNAModelSizes.SIZE_60M: "zehui127/Omni-DNA-60M",
    # OmniDNAModelSizes.SIZE_116M: "zehui127/Omni-DNA-116M",
    # OmniDNAModelSizes.SIZE_300M: "zehui127/Omni-DNA-300M",
    # OmniDNAModelSizes.SIZE_700M: "zehui127/Omni-DNA-700M",
    OmniDNAModelSizes.SIZE_1B: "zehui127/Omni-DNA-1B",
}


hf_pin_revision_mapping = {
    # OmniDNAModelSizes.SIZE_20M: "7d6a2011defe50672570e0bcc7ff9358e2b03103",
    # OmniDNAModelSizes.SIZE_60M: "e86e410892a99c12bc133bcbfb9306e5ca6694f8",
    # OmniDNAModelSizes.SIZE_116M: "5febae866ecd9786901c2f3f380403c25c7dffa6",
    # OmniDNAModelSizes.SIZE_300M: "88beedc1f5425d06e9bb438b9f02de500826c035",
    # OmniDNAModelSizes.SIZE_700M: "a6107a6211b4309c8edc2125e04f213badc8f189",
    OmniDNAModelSizes.SIZE_1B: "ca1be6d00203880e66210b991eea5ff7fd1e6bcb",
}


### Omni-DNA Modal Resource Specs

OMNI_DNA_VARIANT_RESOURCE_SPECS = {
    # OmniDNAModelSizes.SIZE_20M: ModalResourceSpec(
    #     cpu=2.0,
    #     memory=4 * 1024,  # 4 GB
    #     gpu=ModalGPU.T4,
    # ),
    # OmniDNAModelSizes.SIZE_60M: ModalResourceSpec(
    #     cpu=2.0,
    #     memory=4 * 1024,
    #     gpu=ModalGPU.T4,
    # ),
    # OmniDNAModelSizes.SIZE_116M: ModalResourceSpec(
    #     cpu=2.0,
    #     memory=8 * 1024,
    #     gpu=ModalGPU.T4,
    # ),
    # OmniDNAModelSizes.SIZE_300M: ModalResourceSpec(
    #     cpu=3.0,
    #     memory=10 * 1024,  # 10 GB
    #     gpu=ModalGPU.T4,
    # ),
    # OmniDNAModelSizes.SIZE_700M: ModalResourceSpec(
    #     cpu=4.0,
    #     memory=16 * 1024,
    #     gpu=ModalGPU.T4,
    # ),
    OmniDNAModelSizes.SIZE_1B: ModalResourceSpec(
        cpu=4.0,
        memory=16 * 1024,
        gpu=ModalGPU.L4,
    ),
}


# Omni-DNA configuration:
# - Axes: MODEL_SIZE (20m, 60m, 116m, 300m, 700m, 1b)
# - Actions: encode, log_prob
MODEL_FAMILY = ModelFamily(
    base_model_slug=OmniDNAParams.base_model_slug,
    modal_class_name="OmniDNAModel",
    display_name=OmniDNAParams.display_name,
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE],
        input_molecule=[InputMolecule.DNA],
        task=[Task.EMBEDDING, Task.PROPERTY_PREDICTION],
        output_modality=[OutputModality.EMBEDDING, OutputModality.LOG_PROBABILITIES],
        architecture=[Architecture.TRANSFORMER],
    ),
    # Two actions: encode and log_prob
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.ENCODE,
            request_schema=OmniDNAEncodeRequest,
            response_schema=OmniDNAEncodeResponse,
        ),
        ActionSchemaMap(
            name=ModelActions.LOG_PROB,
            request_schema=OmniDNALogProbRequest,
            response_schema=OmniDNALogProbResponse,
        ),
    ],
    # Single axis: MODEL_SIZE with values 20m, 60m, 116m, 300m, 700m, 1b
    variant_axes={
        "MODEL_SIZE": list(OmniDNAModelSizes),
    },
    # Resource function looks up the correct spec from the schema
    resource_function=lambda cfg: OMNI_DNA_VARIANT_RESOURCE_SPECS[
        OmniDNAModelSizes(cfg["MODEL_SIZE"])
    ],
    # Explicit naming function: returns (modal_app_name, public_api_slug)
    # Multi-variant: both return "omni-dna-{variant}"
    naming_function=lambda base_slug, cfg: (
        f"{base_slug}-{cfg['MODEL_SIZE']}" if cfg else base_slug,
        f"{base_slug}-{cfg['MODEL_SIZE']}" if cfg else base_slug,
    ),
)
