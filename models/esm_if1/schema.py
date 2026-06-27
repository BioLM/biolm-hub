from typing import Annotated

from pydantic import BeforeValidator, Field

from models.commons.data.structure_validator import validate_pdb
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import RequestModel, ResponseModel
from models.commons.util.config import max_pdb_str_len

### ESM-IF1 Params


class ESMIF1Params(ModelParams):
    params_version = "v1"
    display_name = "ESM-IF1 Inverse Fold"
    base_model_slug = "esm-if1"
    log_identifier = "ESM-IF1"
    batch_size = 1


### ESM-IF1 Request


class ESMIF1GenerateParams(RequestModel):
    chain: str = Field(default="A", max_length=1)
    num_samples: int = Field(default=1, ge=1, le=3)
    temperature: float = Field(default=0.6, ge=0.0, le=8.0)
    multichain_backbone: bool = Field(default=False)
    seed: int | None = None  # NEW: For reproducibility control


class ESMIF1GenerateRequestItem(RequestModel):
    pdb: Annotated[
        str,
        BeforeValidator(validate_pdb),
        Field(..., min_length=1, max_length=max_pdb_str_len),
    ]


class ESMIF1GenerateRequest(RequestModel):
    params: ESMIF1GenerateParams
    items: Annotated[
        list[ESMIF1GenerateRequestItem],
        Field(min_length=1, max_length=ESMIF1Params.batch_size),
    ]


### ESM-IF1 Response


class ESMIF1GenerateResponseSample(RequestModel):
    sequence: str
    recovery: float


ESMIF1GenerateResponseResult = list[ESMIF1GenerateResponseSample]


class ESMIF1GenerateResponse(ResponseModel):
    results: list[ESMIF1GenerateResponseResult]
