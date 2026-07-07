from typing import Annotated

from pydantic import BeforeValidator, Field

from models.commons.data.validator import validate_smiles
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import RequestModel, ResponseModel

### ChemBERTa Model Parameters


class ChemBERTaParams(ModelParams):
    display_name = "ChemBERTa"
    base_model_slug = "chemberta"
    log_identifier = "CHEMBERTA"
    weights_version = "v1"
    batch_size = 16
    # Character cap on the input SMILES string, enforced by the request schema.
    # 512 characters comfortably covers drug-like and most natural-product SMILES.
    max_sequence_len = 512
    # Token-count truncation limit passed to the HuggingFace tokenizer. RoBERTa
    # has max_position_embeddings=512 and padding_idx=1, so position ids start at
    # 2 — usable positions (including <s>/</s>) are 512 - 2 = 510. The byte-level
    # BPE SMILES tokenizer yields fewer tokens than characters, so this rarely
    # binds in practice; it is a safety cap against pathologically long inputs.
    max_token_len = 510


### ChemBERTa Requests


class ChemBERTaEncodeRequestItem(RequestModel):
    smiles: Annotated[
        str,
        BeforeValidator(validate_smiles),
        Field(
            ...,
            min_length=1,
            max_length=ChemBERTaParams.max_sequence_len,
            description="A small molecule represented as a SMILES string.",
        ),
    ]


class ChemBERTaEncodeRequest(RequestModel):
    items: Annotated[
        list[ChemBERTaEncodeRequestItem],
        Field(
            ...,
            min_length=1,
            max_length=ChemBERTaParams.batch_size,
            description="Batch of inputs to process in a single request. Up to 16 molecules per request.",
        ),
    ]


class ChemBERTaLogProbRequestItem(RequestModel):
    smiles: Annotated[
        str,
        BeforeValidator(validate_smiles),
        Field(
            ...,
            min_length=1,
            max_length=ChemBERTaParams.max_sequence_len,
            description="A small molecule represented as a SMILES string.",
        ),
    ]


class ChemBERTaLogProbRequest(RequestModel):
    items: Annotated[
        list[ChemBERTaLogProbRequestItem],
        Field(
            ...,
            min_length=1,
            max_length=ChemBERTaParams.batch_size,
            description="Batch of inputs to process in a single request. Up to 16 molecules per request.",
        ),
    ]


### ChemBERTa Responses


class ChemBERTaEncodeResponseResult(ResponseModel):
    embedding: list[float] = Field(
        description="Mean-pooled embedding vector for the molecule (768 dimensions)."
    )


class ChemBERTaEncodeResponse(ResponseModel):
    results: list[ChemBERTaEncodeResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items."
    )


class ChemBERTaLogProbResponseResult(ResponseModel):
    log_prob: float = Field(
        description="Pseudo-log-likelihood of the sequence under the model."
    )


class ChemBERTaLogProbResponse(ResponseModel):
    results: list[ChemBERTaLogProbResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items."
    )
