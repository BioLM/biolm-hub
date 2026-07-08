from typing import Annotated

from pydantic import BeforeValidator, Field

from models.commons.data.structure_validator import validate_pdb
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import RequestModel, ResponseModel
from models.commons.util.config import max_pdb_str_len

### ESM-IF1 Params


class ESMIF1Params(ModelParams):
    weights_version = "v1"
    display_name = "ESM-IF1 Inverse Fold"
    base_model_slug = "esm-if1"
    log_identifier = "ESM-IF1"
    batch_size = 1


### ESM-IF1 Request


class ESMIF1GenerateParams(RequestModel):
    chain: str = Field(
        default="A",
        max_length=1,
        description='Chain identifier to redesign (e.g. "A").',
    )
    num_samples: int = Field(
        default=1,
        ge=1,
        le=3,
        description="Number of sequences to generate per input.",
    )
    temperature: float = Field(
        default=0.6,
        ge=0.0,
        le=8.0,
        description="Sampling temperature; higher values increase diversity.",
    )
    multichain_backbone: bool = Field(
        default=False,
        description="Use backbone coordinates from all chains while designing only the selected chain (not yet supported).",
    )
    seed: int | None = Field(
        default=None,
        description="Random seed for reproducible sampling.",
    )


class ESMIF1GenerateRequestItem(RequestModel):
    pdb: Annotated[
        str,
        BeforeValidator(validate_pdb),
        Field(
            ...,
            min_length=1,
            max_length=max_pdb_str_len,
            description="Input structure in PDB format.",
        ),
    ]


class ESMIF1GenerateRequest(RequestModel):
    params: ESMIF1GenerateParams = Field(
        default_factory=ESMIF1GenerateParams,
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: Annotated[
        list[ESMIF1GenerateRequestItem],
        Field(
            min_length=1,
            max_length=ESMIF1Params.batch_size,
            description="Batch of inputs to process in a single request. Exactly one structure per request.",
        ),
    ]


### ESM-IF1 Response


class ESMIF1GenerateResponseSample(ResponseModel):
    sequence: str = Field(
        description="A protein sequence in single-letter amino-acid codes."
    )
    recovery: float = Field(
        description="Fraction of positions matching the native sequence (0.0–1.0)."
    )


ESMIF1GenerateResponseResult = list[ESMIF1GenerateResponseSample]


class ESMIF1GenerateResponse(ResponseModel):
    results: list[ESMIF1GenerateResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items."
    )
