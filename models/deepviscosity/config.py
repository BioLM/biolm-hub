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
from models.deepviscosity.schema import (
    DeepViscosityParams,
    DeepViscosityPredictRequest,
    DeepViscosityPredictResponse,
)

# DeepViscosity Modal Resource Specs - CPU only
# Memory: 2GB for TensorFlow + 102 ANN models + 3 CNN models + scaler
DeepViscosityResourceSpec = ModalResourceSpec(
    cpu=1.0,
    memory=2048,
    gpu=None,
)

# DeepViscosity configuration:
# - Axes: None (single variant)
# - Actions: predict
MODEL_FAMILY = ModelFamily(
    base_model_slug=DeepViscosityParams.base_model_slug,
    modal_class_name="DeepViscosityModel",
    display_name=DeepViscosityParams.display_name,
    tags=ModelTags(
        input_modality=[InputModality.SEQUENCE],
        input_molecule=[InputMolecule.ANTIBODY],
        task=[Task.PROPERTY_PREDICTION],
        output_modality=[OutputModality.CLASS_LABEL, OutputModality.SCALAR],
        architecture=[Architecture.ALGORITHMIC],
    ),
    action_schemas=[
        ActionSchemaMap(
            name=ModelActions.PREDICT,
            request_schema=DeepViscosityPredictRequest,
            response_schema=DeepViscosityPredictResponse,
        )
    ],
    variant_axes={},
    resource_function=lambda cfg: DeepViscosityResourceSpec,
    naming_function=lambda base_slug, cfg: (base_slug, base_slug),
)
