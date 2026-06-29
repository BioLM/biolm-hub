from typing import Annotated, Optional

from pydantic import (
    AliasChoices,
    BeforeValidator,
    ConfigDict,
    Field,
)

from models.commons.data.validator import validate_aa_extended
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

### AbodyBuilder3 Params


class AbodyBuilder3Params(ModelParams):
    weights_version = "v1"
    display_name = "ABodyBuilder3"
    base_model_slug = "abodybuilder3"
    log_identifier = "ABodyBuilder3"
    batch_size = 4
    max_sequence_len = 2048


### AbodyBuilder3 Model Types


class AbodyBuilder3ModelTypes(EnhancedStringEnum):
    LANGUAGE = "language"
    PLDDT = "plddt"


### AbodyBuilder3 Request


class AbodyBuilder3PredictRequestParams(RequestModel):
    plddt: bool = Field(
        default=False,
        description="Whether to return per-residue pLDDT confidence scores in the response.",
    )
    seed: Optional[int] = Field(
        default=42,
        description="Random seed for reproducible sampling.",
    )


class AbodyBuilder3PredictRequestItem(RequestModel):
    # Canonical antibody field names; old `H`/`L` accepted via input alias.
    model_config = ConfigDict(populate_by_name=True)

    heavy_chain: Annotated[
        str,
        BeforeValidator(validate_aa_extended),
        Field(
            ...,
            min_length=1,
            max_length=AbodyBuilder3Params.max_sequence_len,
            validation_alias=AliasChoices("heavy_chain", "H"),
            description="Antibody heavy-chain amino-acid sequence.",
        ),
    ]

    light_chain: Annotated[
        str,
        BeforeValidator(validate_aa_extended),
        Field(
            ...,
            min_length=1,
            max_length=AbodyBuilder3Params.max_sequence_len,
            validation_alias=AliasChoices("light_chain", "L"),
            description="Antibody light-chain amino-acid sequence.",
        ),
    ]


class AbodyBuilder3PredictRequest(RequestModel):
    params: Optional[AbodyBuilder3PredictRequestParams] = Field(
        default=AbodyBuilder3PredictRequestParams(),
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: Annotated[
        list[AbodyBuilder3PredictRequestItem],
        Field(
            min_length=1,
            max_length=AbodyBuilder3Params.batch_size,
            description="Batch of inputs to process in a single request. Up to 4 sequence pairs per request.",
        ),
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
    pdb: str = Field(description="Predicted structure in PDB format.")
    plddt: Optional[list[list[float]]] = Field(
        default=None,
        description="Per-residue pLDDT confidence score (0–100; higher is more confident).",
    )


class AbodyBuilder3PredictResponse(ResponseModel):
    results: list[AbodyBuilder3PredictResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items."
    )
