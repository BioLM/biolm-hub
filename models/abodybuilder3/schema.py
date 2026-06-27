from typing import Annotated, Optional

from pydantic import (
    BeforeValidator,
    Field,
)

from models.commons.data.validator import validate_aa_extended
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)
from models.commons.model.schema import ModalGPU, ModalResourceSpec

### AbodyBuilder3 Params


class AbodyBuilder3Params(ModelParams):
    params_version = "v1"
    display_name = "AbodyBuilder3"
    base_model_slug = "abodybuilder3"
    log_identifier = "AbodyBuilder3"
    batch_size = 4
    max_sequence_len = 2048


### AbodyBuilder3 Model Types


class AbodyBuilder3ModelTypes(EnhancedStringEnum):
    LANGUAGE = "language"
    PLDDT = "plddt"


### AbodyBuilder3 Modal Resource Specs

ABODYBUILDER3_VARIANT_RESOURCE_SPECS = {
    AbodyBuilder3ModelTypes.PLDDT: ModalResourceSpec(
        cpu=2.0, memory=8 * 1024, gpu=None  # 8GB RAM
    ),
    AbodyBuilder3ModelTypes.LANGUAGE: ModalResourceSpec(
        cpu=4.0, memory=12 * 1024, gpu=ModalGPU.L40S  # 48GB RAM
    ),
}


### AbodyBuilder3 Request


class AbodyBuilder3PredictRequestParams(RequestModel):
    plddt: bool = False
    seed: Optional[int] = 42


class AbodyBuilder3PredictRequestItem(RequestModel):
    H: Annotated[
        str,
        BeforeValidator(
            validate_aa_extended
        ),  # TODO: check if extended or unambiguous should be validated
        Field(None, min_length=1, max_length=AbodyBuilder3Params.max_sequence_len),
    ]

    L: Annotated[
        str,
        BeforeValidator(validate_aa_extended),
        Field(None, min_length=1, max_length=AbodyBuilder3Params.max_sequence_len),
    ]


class AbodyBuilder3PredictRequest(RequestModel):
    params: Optional[AbodyBuilder3PredictRequestParams] = (
        AbodyBuilder3PredictRequestParams()
    )
    items: Annotated[
        list[AbodyBuilder3PredictRequestItem],
        Field(min_length=1, max_length=AbodyBuilder3Params.batch_size),
    ]


### AbodyBuilder3 Response


class AbodyBuilder3PredictResponseResult(ResponseModel):
    model_config = {
        "populate_by_name": True,  # Ensures alias names work as expected
        "json_schema_extra": {
            "exclude_unset": True,  # Excludes unset (None) fields from the output
            "exclude_none": True,  # Ensures that None fields do not appear in JSON
        },
    }
    pdb: str
    plddt: Optional[list[list[float]]] = None


class AbodyBuilder3PredictResponse(ResponseModel):
    results: list[AbodyBuilder3PredictResponseResult]
