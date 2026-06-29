from typing import Annotated

from pydantic import BeforeValidator, Field

from models.commons.data.validator import validate_aa_unambiguous
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

### ProGen2 Params


class ProGen2Params(ModelParams):
    display_name = "ProGen2"
    base_model_slug = "progen2"
    log_identifier = "ProGen2"
    params_version = "v1"
    batch_size = 1
    max_sequence_len = 512


class ProGen2ModelTypes(EnhancedStringEnum):
    OAS = "oas"
    MEDIUM = "medium"
    LARGE = "large"
    BFD90 = "bfd90"


### ProGen2 Request


class ProGen2GenerateParams(RequestModel):
    temperature: float = Field(
        default=0.8,
        gt=0.0,
        le=8.0,
        description="Sampling temperature; higher values increase diversity.",
    )
    top_p: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Nucleus (top-p) sampling threshold.",
    )
    num_samples: int = Field(
        default=1,
        ge=1,
        le=3,
        description="Number of sequences to generate per input.",
    )
    max_length: int = Field(
        default=128,
        ge=12,
        le=ProGen2Params.max_sequence_len,
        description="Maximum length of the generated sequence.",
    )
    seed: int | None = Field(
        default=None,
        description="Random seed for reproducible sampling.",
    )


class ProGen2GenerateRequestItem(RequestModel):
    context: Annotated[
        str,
        BeforeValidator(validate_aa_unambiguous),
        Field(
            ...,
            min_length=1,
            max_length=ProGen2Params.max_sequence_len,
            description="Amino acid seed sequence (unambiguous codes) to condition generation; the output begins with this context.",
        ),
    ]


class ProGen2GenerateRequest(RequestModel):
    params: ProGen2GenerateParams = Field(
        default_factory=ProGen2GenerateParams,
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: Annotated[
        list[ProGen2GenerateRequestItem],
        Field(
            min_length=1,
            max_length=ProGen2Params.batch_size,
            description="Batch of inputs to process in a single request. Up to 1 sequence per request.",
        ),
    ]


### ProGen2 Response


class ProGen2GenerateResponseGenerated(ResponseModel):
    sequence: str = Field(
        description="Generated protein sequence (context prefix + completion), with terminal tokens stripped.",
    )
    ll_sum: float = Field(
        description="Summed bidirectional log-likelihood (forward + reverse passes averaged); more negative means less likely.",
    )
    ll_mean: float = Field(
        description="Mean bidirectional log-likelihood per position; more negative means less likely per residue.",
    )


ProGen2GenerateResponseResult = list[ProGen2GenerateResponseGenerated]


class ProGen2GenerateResponse(ResponseModel):
    results: list[ProGen2GenerateResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )
