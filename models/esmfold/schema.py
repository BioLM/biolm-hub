from typing import Annotated

from pydantic import BeforeValidator, Field

from models.commons.data.validator import (
    AAExtendedPlusExtra,
    UpToNNonConsecutiveOccurrencesOf,
)
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import RequestModel, ResponseModel

### ESMFold Params


class ESMFoldParams(ModelParams):
    params_version = "v1"
    display_name = "ESMFold"
    base_model_slug = "esmfold"
    log_identifier = "ESMFold"
    batch_size = 2
    max_sequence_len = 768
    max_n_multimers = 4  # Maximum number of chains in a sequence
    max_tokens_per_batch = (
        1024  # Maximum total residue tokens across sequences in one GPU forward pass
    )


### ESMFold Request


class ESMFoldPredictRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(
            UpToNNonConsecutiveOccurrencesOf(
                token=":",
                max_count=ESMFoldParams.max_n_multimers - 1,
            )
        ),
        BeforeValidator(AAExtendedPlusExtra(extra=[":"])),
        Field(
            min_length=1,
            max_length=ESMFoldParams.max_sequence_len
            + ESMFoldParams.max_n_multimers
            - 1,
            description='A protein sequence in single-letter amino-acid codes; for complexes, separate up to 4 chains with ":" (768 residues total).',
        ),
    ]


class ESMFoldPredictRequest(RequestModel):
    items: Annotated[
        list[ESMFoldPredictRequestItem],
        Field(
            min_length=1,
            max_length=ESMFoldParams.batch_size,
            description="Batch of inputs to process in a single request. Up to 2 sequences per request.",
        ),
    ]


### ESMFold Response


class ESMFoldPredictResponseResult(ResponseModel):
    pdb: str = Field(description="Predicted structure in PDB format.")
    mean_plddt: float = Field(
        description="Mean per-residue pLDDT confidence score (0–100); higher values indicate more confident predictions."
    )
    ptm: float = Field(
        description="Predicted TM-score (pTM) for the overall structure (0–1)."
    )


class ESMFoldPredictResponse(ResponseModel):
    results: list[ESMFoldPredictResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items."
    )
