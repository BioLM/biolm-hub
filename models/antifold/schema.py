from functools import partial
from typing import Annotated, Optional, Union

from pydantic import (
    AliasChoices,
    BeforeValidator,
    ConfigDict,
    Field,
    PrivateAttr,
    model_validator,
)

from models.commons.data.structure_validator import validate_pdb
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)
from models.commons.util.config import max_pdb_str_len

### AntiFold Params


class AntiFoldParams(ModelParams):
    weights_version = "v1"
    display_name = "AntiFold"
    base_model_slug = "antifold"
    log_identifier = "AntiFold"
    batch_size = 32
    generate_batch_size = 1


class AntiFoldValidRegions(EnhancedStringEnum):
    ALL = "all"
    ALLH = "allH"
    ALLL = "allL"
    FWH = "FWH"
    FWL = "FWL"
    CDRH = "CDRH"
    CDRL = "CDRL"
    FW1 = "FW1"
    FWH1 = "FWH1"
    FWL1 = "FWL1"
    CDR1 = "CDR1"
    CDRH1 = "CDRH1"
    CDRL1 = "CDRL1"
    FW2 = "FW2"
    FWH2 = "FWH2"
    FWL2 = "FWL2"
    CDR2 = "CDR2"
    CDRH2 = "CDRH2"
    CDRL2 = "CDRL2"
    FW3 = "FW3"
    FWH3 = "FWH3"
    FWL3 = "FWL3"
    CDR3 = "CDR3"
    CDRH3 = "CDRH3"
    CDRL3 = "CDRL3"
    FW4 = "FW4"
    FWH4 = "FWH4"
    FWL4 = "FWL4"


def parse_pdb_string(pdb_string: str) -> tuple[dict[str, int], list[str]]:
    """
    Parses a PDB string, returning a dict of chain -> count of unique residues,
    and a sorted list of the chain IDs found.
    """
    chain_residues: dict[str, set[tuple[str, str]]] = {}
    chains: set[str] = set()

    for line in pdb_string.splitlines():
        if line.startswith("ATOM") or line.startswith("HETATM"):
            chain_id = line[21]
            res_num = line[22:26].strip()
            res_insertion = line[26].strip()  # Include insertion code if present
            residue_id = (res_num, res_insertion)

            if chain_id not in chain_residues:
                chain_residues[chain_id] = set()
            chain_residues[chain_id].add(residue_id)
            chains.add(chain_id)

    # Convert sets to counts
    chain_residue_counts = {
        chain: len(residues) for chain, residues in chain_residues.items()
    }
    chains_list = sorted(chains)  # Sorting to have a consistent order

    return chain_residue_counts, chains_list


def validate_chain_id(
    chains: list[str],
    chain_id: str,
) -> None:
    """
    Validates that every chain id is actually present
    in the specified PDB.
    """

    if chain_id not in chains:
        raise ValueError(
            f"Chain id {chain_id} is invalid not " f"detected in PDB chains: {chains}"
        )


def validate_positions(
    chain_counts: dict[str, int],
    regions: Union[list[AntiFoldValidRegions], list[int]],
    chain_id: str,
) -> None:
    """
    Validates that every position in regions is actually present
    in the specified PDB.
    """
    if all(isinstance(r, AntiFoldValidRegions) for r in regions):
        return
    for pos in regions:

        if not 1 <= int(pos) <= chain_counts[chain_id]:
            raise ValueError(
                f"Region position specification {pos} has invalid position greater than "
                f"chain length: {chain_counts[chain_id]}"
            )


### AntiFold Requests


class AntiFoldEncodeIncludeOptions(EnhancedStringEnum):
    MEAN = "mean"  # mean embedding (default)
    PER_RESIDUE = "per_residue"  # per-residue embeddings
    RESIDUE = "per_residue"  # deprecated alias of PER_RESIDUE (back-compat)
    LOGITS = "logits"  # logits

    @classmethod
    def _missing_(cls, value: object) -> "AntiFoldEncodeIncludeOptions | None":
        # Back-compat: legacy per-residue value, normalized to the canonical name.
        if isinstance(value, str) and value == "residue":
            return cls.PER_RESIDUE
        return None


class AntiFoldGenerateIncludeOptions(EnhancedStringEnum):
    LOGPROBS = "logprobs"  # softmax logprobs
    LOGITS = "logits"  # logits


class AntiFoldPredictRequestParams(RequestModel):
    # These are PDB chain SELECTORS (which chain in the input PDB), not sequences,
    # so they take the canonical `_id` suffix. Old names accepted via alias.
    model_config = ConfigDict(populate_by_name=True)

    heavy_chain_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices(
            "heavy_chain_id",
            "heavy_chain",
            # back-compat: nanobody VHH is heavy-chain-only; accept old field names
            "nanobody_chain_id",
            "nanobody_chain",
        ),
        description="PDB chain identifier for the antibody heavy chain (VH) or nanobody (VHH) chain. For nanobody inputs, omit light_chain_id.",
    )
    light_chain_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("light_chain_id", "light_chain"),
        description="PDB chain identifier for the antibody light chain (VL).",
    )
    antigen_chain_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("antigen_chain_id", "antigen_chain"),
        description="Optional PDB chain identifier for the antigen chain, providing structural context during inference.",
    )

    # Private attribute to store the inferred "chain mode"
    _custom_chain_mode: Optional[bool] = PrivateAttr(default=False)

    @model_validator(mode="after")
    def validate_and_infer_type(self) -> "AntiFoldPredictRequestParams":
        """
        Infer chain type and ensure valid field combos.
        """
        heavy, light, antigen = (
            self.heavy_chain_id,
            self.light_chain_id,
            self.antigen_chain_id,
        )

        if not any([heavy, light]):
            raise ValueError(
                "At least one of heavy_chain_id or light_chain_id must be specified."
            )
        if light and not heavy:
            raise ValueError(
                "Cannot provide just `light_chain_id`. Provide both "
                "`heavy_chain_id` and `light_chain_id` and set `exclude_heavy` or "
                "`exclude_light` to restrict sampling to one chain"
            )
        if heavy and not light:
            self._custom_chain_mode = True
        if antigen:
            self._custom_chain_mode = True

        return self


class AntiFoldEncodeRequestParams(AntiFoldPredictRequestParams):
    include: list[AntiFoldEncodeIncludeOptions] = Field(
        default_factory=partial(list, [AntiFoldEncodeIncludeOptions.MEAN]),
        description="Optional outputs to compute and include in the response.",
    )


class AntiFoldBaseRequestItem(RequestModel):
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


class AntiFoldPredictRequest(RequestModel):
    params: AntiFoldPredictRequestParams = Field(
        description="Parameters controlling this action; required because they carry the PDB chain selectors (at least one of heavy_chain_id / light_chain_id must be provided).",
    )
    items: list[AntiFoldBaseRequestItem] = Field(
        min_length=1,
        max_length=AntiFoldParams.batch_size,
        description="Batch of inputs to process in a single request. Up to 32 structures per request.",
    )

    @model_validator(mode="after")
    def validate_params(self) -> "AntiFoldPredictRequest":  # noqa: C901
        # FIXME(noqa: C901): Refactor to reduce complexity below the linter's threshold.

        params = self.params
        items = self.items

        if not items:
            raise ValueError("Items must be populated for params validation")
        if not params:
            raise ValueError("Params must be populated for validation")

        for item in items:
            chain_counts, chain_list = parse_pdb_string(item.pdb)

            if params.heavy_chain_id:
                validate_chain_id(chain_list, params.heavy_chain_id)
            if params.light_chain_id:
                validate_chain_id(chain_list, params.light_chain_id)
            if params.antigen_chain_id:
                validate_chain_id(chain_list, params.antigen_chain_id)

        return self


class AntiFoldEncodeRequest(AntiFoldPredictRequest):
    params: AntiFoldEncodeRequestParams = Field(
        description="Parameters controlling this action; required because they carry the PDB chain selectors (at least one of heavy_chain_id / light_chain_id must be provided).",
    )


class AntiFoldGenerateRequestParams(AntiFoldPredictRequestParams):
    seed: Optional[int] = Field(
        default=None,
        description="Random seed for reproducible sampling.",
    )
    include: Optional[list[AntiFoldGenerateIncludeOptions]] = Field(
        default=None,
        description="Optional outputs to compute and include in the response.",
    )
    num_seq_per_target: int = Field(
        default=1,
        ge=1,
        le=50000,
        description="Number of sequences to generate per input.",
    )
    sampling_temp: float = Field(
        default=0.2,
        ge=0.0,
        le=4.0,
        description="Sampling temperature; higher values increase diversity.",
    )
    regions: Union[list[AntiFoldValidRegions], list[int]] = Field(
        default_factory=partial(
            list,
            [
                AntiFoldValidRegions.CDR1,
                AntiFoldValidRegions.CDR2,
                AntiFoldValidRegions.CDR3,
            ],
        ),
        description='Antibody regions to redesign; accepts named regions (e.g. "CDR3", "FWH1") or a list of 1-based residue positions.',
    )
    limit_expected_variation: Optional[bool] = Field(
        default=False,
        description="If true, constrain sequence sampling to the natural variation range observed in antibody databases.",
    )
    exclude_heavy: Optional[bool] = Field(
        default=False,
        description="If true, exclude the heavy chain from sequence sampling (the light chain is designed instead).",
    )
    exclude_light: Optional[bool] = Field(
        default=False,
        description="If true, exclude the light chain from sequence sampling (the heavy chain is designed instead).",
    )


class AntiFoldGenerateRequest(RequestModel):
    params: AntiFoldGenerateRequestParams = Field(
        description="Parameters controlling this action; required because they carry the PDB chain selectors (at least one of heavy_chain_id / light_chain_id must be provided).",
    )
    items: list[AntiFoldBaseRequestItem] = Field(
        min_length=1,
        max_length=AntiFoldParams.generate_batch_size,
        description="Batch of inputs to process in a single request. Up to 1 structure per request.",
    )

    @model_validator(mode="after")
    def validate_params(self) -> "AntiFoldGenerateRequest":  # noqa: C901
        # FIXME(noqa: C901): Refactor to reduce complexity below the linter's threshold.

        params = self.params
        items = self.items

        if not items:
            raise ValueError("Items must be populated for params validation")

        for item in items:
            chain_counts, chain_list = parse_pdb_string(item.pdb)

            if params.heavy_chain_id:
                validate_chain_id(chain_list, params.heavy_chain_id)
                validate_positions(chain_counts, params.regions, params.heavy_chain_id)
            if params.light_chain_id:
                validate_chain_id(chain_list, params.light_chain_id)
                validate_positions(chain_counts, params.regions, params.light_chain_id)
            if params.antigen_chain_id:
                validate_chain_id(chain_list, params.antigen_chain_id)

        return self


### AntiFold Responses


class AntiFoldEncodeResponseResult(ResponseModel):
    model_config = {
        "populate_by_name": True,  # Ensures alias names work
        "json_schema_extra": {
            "exclude_unset": True,  # Excludes unset (None) fields from the output
            "exclude_none": True,  # Ensures that None fields do not appear in JSON
        },
    }

    embeddings: Optional[list[float]] = Field(
        default=None,
        description="Mean-pooled embedding vector for the sequence.",
    )
    residue_embeddings: Optional[list[list[float]]] = Field(
        default=None,
        description="Per-residue embedding vectors.",
    )
    logits: Optional[list[list[float]]] = Field(
        default=None,
        description="Per-position logits over the model vocabulary.",
    )
    pdb_posins: Optional[list[int]] = Field(
        default=None,
        description="IMGT-based residue position numbers for each position in the output.",
    )
    pdb_chain: Optional[list[str]] = Field(
        default=None,
        description="PDB chain identifier for each output position.",
    )
    pdb_res: Optional[list[str]] = Field(
        default=None,
        description="Native amino-acid residue type at each output position.",
    )
    top_res: Optional[list[str]] = Field(
        default=None,
        description="Highest-probability predicted amino acid at each position.",
    )
    perplexity: Optional[list[float]] = Field(
        default=None,
        description="Per-position perplexity values for the sequence under the model (lower means more likely).",
    )
    vocab_tokens: Optional[list[str]] = Field(
        default=None,
        validation_alias=AliasChoices("vocab_tokens", "vocab"),
        description="Vocabulary token order corresponding to the logits columns.",
    )


class AntiFoldEncodeResponse(ResponseModel):
    results: list[AntiFoldEncodeResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )


class AntiFoldGenerateResponseResultSamples(ResponseModel):
    model_config = {
        "populate_by_name": True,  # Ensures alias names work
        "json_schema_extra": {
            "exclude_unset": True,  # Excludes unset (None) fields from the output
            "exclude_none": True,  # Ensures that None fields do not appear in JSON
        },
    }
    global_score: float = Field(
        description="Mean per-residue inverse-folding log-likelihood over the full antibody sequence given the backbone structure.",
    )
    score: float = Field(
        description="Mean per-residue inverse-folding log-likelihood over the designed region(s) of this sample.",
    )
    # Designed antibody chain sequences. Canonical output names; the upstream
    # AntiFold keys (`heavy`/`light`) are accepted via alias.
    heavy_chain: str = Field(
        validation_alias=AliasChoices("heavy_chain", "heavy"),
        description="Antibody heavy-chain amino-acid sequence.",
    )
    light_chain: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("light_chain", "light"),
        description="Antibody light-chain amino-acid sequence.",
    )
    temperature: float = Field(
        description="Sampling temperature; higher values increase diversity.",
    )
    mutations: int = Field(
        description="Number of amino-acid mutations relative to the native input sequence.",
    )
    seq_recovery: float = Field(
        description="Fraction of positions matching the native sequence (sequence recovery rate, 0–1).",
    )


class AntiFoldGenerateResponseResult(ResponseModel):
    model_config = {
        "populate_by_name": True,  # Ensures alias names work
        "json_schema_extra": {
            "exclude_unset": True,  # Excludes unset (None) fields from the output
            "exclude_none": True,  # Ensures that None fields do not appear in JSON
        },
    }
    sequences: list[AntiFoldGenerateResponseResultSamples] = Field(
        description="Generated antibody sequence samples for this input.",
    )
    logprobs: Optional[list[list[float]]] = Field(
        default=None,
        description="Per-position softmax log-probabilities over the vocabulary (included when logprobs is in the include list).",
    )
    logits: Optional[list[list[float]]] = Field(
        default=None,
        description="Per-position logits over the model vocabulary.",
    )
    pdb_posins: Optional[list[int]] = Field(
        default=None,
        description="IMGT-based residue position numbers for each position in the output.",
    )
    pdb_chain: Optional[list[str]] = Field(
        default=None,
        description="PDB chain identifier for each output position.",
    )
    pdb_res: Optional[list[str]] = Field(
        default=None,
        description="Native amino-acid residue type at each output position.",
    )
    top_res: Optional[list[str]] = Field(
        default=None,
        description="Highest-probability predicted amino acid at each position.",
    )
    perplexity: Optional[list[float]] = Field(
        default=None,
        description="Per-position perplexity values for the sequence under the model (lower means more likely).",
    )
    vocab_tokens: Optional[list[str]] = Field(
        default=None,
        validation_alias=AliasChoices("vocab_tokens", "vocab"),
        description="Vocabulary token order corresponding to the logits columns.",
    )


class AntiFoldGenerateResponse(ResponseModel):
    results: list[AntiFoldGenerateResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )


class AntiFoldLogProbResponseResult(ResponseModel):
    log_prob: float = Field(
        description="Log-likelihood of the sequence under the model.",
    )


class AntiFoldLogProbResponse(ResponseModel):
    results: list[AntiFoldLogProbResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )


class AntiFoldScoreResponseResult(ResponseModel):
    model_config = {
        "populate_by_name": True,  # Ensures alias names work
        "json_schema_extra": {
            "exclude_unset": True,  # Excludes unset (None) fields from the output
            "exclude_none": True,  # Ensures that None fields do not appear in JSON
        },
    }
    global_score: float = Field(
        description="Mean per-residue inverse-folding log-likelihood over the full antibody sequence given the backbone structure.",
    )
    # Scored antibody chain sequences. Canonical output names; the upstream
    # AntiFold keys (`heavy`/`light`) are accepted via alias.
    heavy_chain: str = Field(
        validation_alias=AliasChoices("heavy_chain", "heavy"),
        description="Antibody heavy-chain amino-acid sequence.",
    )
    light_chain: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("light_chain", "light"),
        description="Antibody light-chain amino-acid sequence.",
    )


class AntiFoldScoreResponse(ResponseModel):
    results: list[AntiFoldScoreResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )
