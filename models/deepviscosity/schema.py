from typing import Annotated, Optional

from pydantic import BeforeValidator, Field

from models.commons.data.validator import validate_aa_unambiguous
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import RequestModel, ResponseModel


class DeepViscosityParams(ModelParams):
    """DeepViscosity model parameters."""

    params_version = "v1"
    display_name = "DeepViscosity"
    base_model_slug = "deepviscosity"
    log_identifier = "DEEPVISCOSITY"
    batch_size = 10
    max_sequence_len = 200  # VH/VL Fv regions are typically ~110-130 residues
    min_sequence_len = 50  # Minimum reasonable Fv length


# DeepSP feature names (30 spatial properties)
DEEPSP_FEATURE_NAMES = [
    "SAP_pos_CDRH1",
    "SAP_pos_CDRH2",
    "SAP_pos_CDRH3",
    "SAP_pos_CDRL1",
    "SAP_pos_CDRL2",
    "SAP_pos_CDRL3",
    "SAP_pos_CDR",
    "SAP_pos_Hv",
    "SAP_pos_Lv",
    "SAP_pos_Fv",
    "SCM_neg_CDRH1",
    "SCM_neg_CDRH2",
    "SCM_neg_CDRH3",
    "SCM_neg_CDRL1",
    "SCM_neg_CDRL2",
    "SCM_neg_CDRL3",
    "SCM_neg_CDR",
    "SCM_neg_Hv",
    "SCM_neg_Lv",
    "SCM_neg_Fv",
    "SCM_pos_CDRH1",
    "SCM_pos_CDRH2",
    "SCM_pos_CDRH3",
    "SCM_pos_CDRL1",
    "SCM_pos_CDRL2",
    "SCM_pos_CDRL3",
    "SCM_pos_CDR",
    "SCM_pos_Hv",
    "SCM_pos_Lv",
    "SCM_pos_Fv",
]


class DeepViscosityPredictRequestParams(RequestModel):
    """Parameters for DeepViscosity prediction request."""

    include_deepsp_features: bool = Field(
        default=False,
        description="Include 30 DeepSP spatial property features in response",
    )


class DeepViscosityPredictRequestItem(RequestModel):
    """Single antibody item for DeepViscosity prediction."""

    heavy_chain: Annotated[
        str,
        BeforeValidator(validate_aa_unambiguous),
        Field(
            ...,
            min_length=DeepViscosityParams.min_sequence_len,
            max_length=DeepViscosityParams.max_sequence_len,
            description="Heavy chain variable region (VH) Fv sequence",
        ),
    ]
    light_chain: Annotated[
        str,
        BeforeValidator(validate_aa_unambiguous),
        Field(
            ...,
            min_length=DeepViscosityParams.min_sequence_len,
            max_length=DeepViscosityParams.max_sequence_len,
            description="Light chain variable region (VL) Fv sequence",
        ),
    ]


class DeepViscosityPredictRequest(RequestModel):
    """DeepViscosity prediction request."""

    params: Optional[DeepViscosityPredictRequestParams] = None
    items: Annotated[
        list[DeepViscosityPredictRequestItem],
        Field(min_length=1, max_length=DeepViscosityParams.batch_size),
    ]


class DeepViscosityPredictResponseResult(ResponseModel):
    """Single result from DeepViscosity prediction."""

    viscosity_class: str = Field(
        ...,
        description="Predicted viscosity class: 'low' (<=20 cP) or 'high' (>20 cP)",
    )
    probability_mean: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Mean predicted probability across 102 ensemble models",
    )
    probability_std: float = Field(
        ...,
        ge=0.0,
        description="Standard deviation of predictions across ensemble",
    )
    is_high_viscosity: bool = Field(
        ...,
        description="True if probability_mean >= 0.5 (high viscosity predicted)",
    )
    deepsp_features: Optional[dict[str, float]] = Field(
        default=None,
        description="DeepSP spatial properties (30 features) if requested",
    )


class DeepViscosityPredictResponse(ResponseModel):
    """DeepViscosity prediction response."""

    results: list[DeepViscosityPredictResponseResult]
