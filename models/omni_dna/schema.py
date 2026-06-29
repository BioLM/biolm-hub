from functools import partial
from typing import Annotated, Optional

from pydantic import BeforeValidator, Field

from models.commons.data.validator import validate_dna_unambiguous
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

### Omni-DNA Model Parameters


class OmniDNAParams(ModelParams):
    params_version = "v1"
    display_name = "Omni-DNA"
    base_model_slug = "omni-dna"
    log_identifier = "Omni-DNA"
    batch_size = 2
    max_sequence_len = 2048


class OmniDNAModelSizes(EnhancedStringEnum):
    # SIZE_20M = "20m"
    # SIZE_60M = "60m"
    # SIZE_116M = "116m"
    # SIZE_300M = "300m"
    # SIZE_700M = "700m"
    SIZE_1B = "1b"


### Omni-DNA Requests


class OmniDNAEncodeIncludeOptions(EnhancedStringEnum):
    MEAN = "mean"
    LAST = "last"


class OmniDNAEncodeRequestParams(RequestModel):
    include: list[OmniDNAEncodeIncludeOptions] = Field(
        default_factory=partial(list, [OmniDNAEncodeIncludeOptions.MEAN]),
        description="Optional outputs to compute and include in the response.",
    )


class OmniDNAEncodeRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(validate_dna_unambiguous),
        Field(
            ...,
            min_length=1,
            max_length=OmniDNAParams.max_sequence_len,
            description="A DNA sequence (A/C/G/T).",
        ),
    ]


class OmniDNAEncodeRequest(RequestModel):
    params: OmniDNAEncodeRequestParams = Field(
        default_factory=OmniDNAEncodeRequestParams,
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: Annotated[
        list[OmniDNAEncodeRequestItem],
        Field(
            ...,
            min_length=1,
            max_length=OmniDNAParams.batch_size,
            description="Batch of inputs to process in a single request. Up to 2 sequences per request.",
        ),
    ]


class OmniDNAPredictLogProbRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(validate_dna_unambiguous),
        Field(
            ...,
            min_length=1,
            max_length=OmniDNAParams.max_sequence_len,
            description="A DNA sequence (A/C/G/T).",
        ),
    ]


class OmniDNAPredictLogProbRequest(RequestModel):
    items: Annotated[
        list[OmniDNAPredictLogProbRequestItem],
        Field(
            ...,
            min_length=1,
            max_length=OmniDNAParams.batch_size,
            description="Batch of inputs to process in a single request. Up to 2 sequences per request.",
        ),
    ]


### Omni-DNA Responses


class OmniDNAEncodeResponseEmbedding(RequestModel):
    embedding: list[float] = Field(
        description="Embedding vector for the sequence.",
    )


class OmniDNAEncodeResponseResult(ResponseModel):
    model_config = {
        "populate_by_name": True,  # Ensures alias names work as expected
        "json_schema_extra": {
            "exclude_unset": True,  # Excludes unset (None) fields from the output
            "exclude_none": True,  # Ensures that None fields do not appear in JSON
        },
    }

    mean: Optional[list[OmniDNAEncodeResponseEmbedding]] = Field(
        default=None,
        description='Mean-pooled embeddings over non-padded BPE tokens; present when "mean" is in params.include.',
    )
    last: Optional[list[OmniDNAEncodeResponseEmbedding]] = Field(
        default=None,
        description='Last-token embeddings from the final hidden layer; present when "last" is in params.include.',
    )


class OmniDNAEncodeResponse(ResponseModel):
    results: list[OmniDNAEncodeResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )


class OmniDNAPredictLogProbResponseResult(ResponseModel):
    log_prob: float = Field(
        description="Log-likelihood of the sequence under the model.",
    )


class OmniDNAPredictLogProbResponse(ResponseModel):
    results: list[OmniDNAPredictLogProbResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )
