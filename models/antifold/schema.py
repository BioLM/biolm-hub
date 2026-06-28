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
    params_version = "v1"
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


def parse_pdb_string(pdb_string):
    """
    Parses a PDB string, returning a dict of chain -> count of unique residues,
    and a sorted list of the chain IDs found.
    """
    chain_residues = {}
    chains = set()

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
):
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
    chain_id,
):
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
    RESIDUE = "residue"  # per-residue embeddings
    LOGITS = "logits"  # logits


class AntiFoldGenerateIncludeOptions(EnhancedStringEnum):
    LOGPROBS = "logprobs"  # softmax logprobs
    LOGITS = "logits"  # logits


class AntiFoldPredictRequestParams(RequestModel):
    # These are PDB chain SELECTORS (which chain in the input PDB), not sequences,
    # so they take the canonical `_id` suffix. Old names accepted via alias.
    model_config = ConfigDict(populate_by_name=True)

    heavy_chain_id: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("heavy_chain_id", "heavy_chain")
    )
    light_chain_id: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("light_chain_id", "light_chain")
    )
    nanobody_chain_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("nanobody_chain_id", "nanobody_chain"),
    )
    antigen_chain_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("antigen_chain_id", "antigen_chain"),
    )

    # Private attribute to store the inferred "chain mode"
    _custom_chain_mode: Optional[bool] = PrivateAttr(default=False)

    @model_validator(mode="after")
    def validate_and_infer_type(cls, instance):
        """
        Infer chain type and ensure valid field combos:
          - Otherwise => error.
        """
        heavy, light, nanobody, antigen = (
            instance.heavy_chain_id,
            instance.light_chain_id,
            instance.nanobody_chain_id,
            instance.antigen_chain_id,
        )

        if not any([heavy, light, nanobody]):
            raise ValueError(
                "PDB chain for heavy_chain_id and light_chain_id or "
                "nanobody_chain_id must be specified"
            )
        if nanobody and (heavy or light):
            instance._custom_chain_mode = True
            raise ValueError(
                "Cannot provide both `nanobody_chain_id` and "
                "(`heavy_chain_id`, `light_chain_id`). Pick one."
            )

        if light and not heavy:
            raise ValueError(
                "Cannot provide just `light_chain_id`. Provide both "
                "`heavy_chain_id` and `light_chain_id` and set `exclude_heavy` or "
                "`exclude_light` to restrict sampling to one chain"
            )
        if heavy and not light:
            instance._custom_chain_mode = True
        if nanobody:
            instance._custom_chain_mode = True
        if antigen:
            instance._custom_chain_mode = True

        return instance


class AntiFoldEncodeRequestParams(AntiFoldPredictRequestParams):
    include: list[AntiFoldEncodeIncludeOptions] = Field(
        default_factory=partial(list, [AntiFoldEncodeIncludeOptions.MEAN])
    )


class AntiFoldBaseRequestItem(RequestModel):
    pdb: Annotated[
        str,
        BeforeValidator(validate_pdb),
        Field(..., min_length=1, max_length=max_pdb_str_len),
    ]


class AntiFoldPredictRequest(RequestModel):
    params: AntiFoldPredictRequestParams
    items: list[AntiFoldBaseRequestItem] = Field(
        min_length=1, max_length=AntiFoldParams.batch_size
    )

    @model_validator(mode="after")
    def validate_params(cls, instance):  # noqa: C901
        # FIXME(noqa: C901): Refactor to reduce complexity below the linter's threshold.

        params = instance.params
        items = instance.items

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
            if params.nanobody_chain_id:
                validate_chain_id(chain_list, params.nanobody_chain_id)
            if params.antigen_chain_id:
                validate_chain_id(chain_list, params.antigen_chain_id)

        return instance


class AntiFoldEncodeRequest(AntiFoldPredictRequest):
    params: AntiFoldEncodeRequestParams


class AntiFoldGenerateRequestParams(AntiFoldPredictRequestParams):
    seed: Optional[int] = None
    include: Optional[list[AntiFoldGenerateIncludeOptions]] = None
    num_seq_per_target: int = Field(default=1, ge=1, le=50000)
    sampling_temp: float = Field(default=0.2, ge=0.0, le=4.0)
    regions: Union[list[AntiFoldValidRegions], list[int]] = Field(
        default_factory=partial(
            list,
            [
                AntiFoldValidRegions.CDR1,
                AntiFoldValidRegions.CDR2,
                AntiFoldValidRegions.CDR3,
            ],
        )
    )
    limit_expected_variation: Optional[bool] = False
    exclude_heavy: Optional[bool] = False
    exclude_light: Optional[bool] = False


class AntiFoldGenerateRequestItem(RequestModel):
    pdb: Annotated[
        str,
        BeforeValidator(validate_pdb),
        Field(..., min_length=1, max_length=max_pdb_str_len),
    ]


class AntiFoldGenerateRequest(RequestModel):
    params: AntiFoldGenerateRequestParams
    items: list[AntiFoldBaseRequestItem] = Field(
        min_length=1, max_length=AntiFoldParams.generate_batch_size
    )

    @model_validator(mode="after")
    def validate_params(cls, instance):  # noqa: C901
        # FIXME(noqa: C901): Refactor to reduce complexity below the linter's threshold.

        params = instance.params
        items = instance.items

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
            if params.nanobody_chain_id:
                validate_chain_id(chain_list, params.nanobody_chain_id)
                validate_positions(
                    chain_counts, params.regions, params.nanobody_chain_id
                )
            if params.antigen_chain_id:
                validate_chain_id(chain_list, params.antigen_chain_id)

        return instance


### AntiFold Responses


class AntiFoldEncodeResponseResult(ResponseModel):
    model_config = {
        "populate_by_name": True,  # Ensures alias names work
        "json_schema_extra": {
            "exclude_unset": True,  # Excludes unset (None) fields from the output
            "exclude_none": True,  # Ensures that None fields do not appear in JSON
        },
    }

    embeddings: Optional[list[float]] = None
    residue_embeddings: Optional[list[list[float]]] = None
    logits: Optional[list[list[float]]] = None
    pdb_posins: Optional[list[int]] = None
    pdb_chain: Optional[list[str]] = None
    pdb_res: Optional[list[str]] = None
    top_res: Optional[list[str]] = None
    perplexity: Optional[list[float]] = None
    vocab: Optional[list[str]] = None


class AntiFoldEncodeResponse(ResponseModel):
    results: list[AntiFoldEncodeResponseResult]


class AntiFoldGenerateResponseResultInput(RequestModel):
    global_score: float
    sequence: str


class AntiFoldGenerateResponseResultSamples(RequestModel):
    model_config = {
        "populate_by_name": True,  # Ensures alias names work
        "json_schema_extra": {
            "exclude_unset": True,  # Excludes unset (None) fields from the output
            "exclude_none": True,  # Ensures that None fields do not appear in JSON
        },
    }
    global_score: float
    score: float
    # Designed antibody chain sequences. Canonical output names; the upstream
    # AntiFold keys (`heavy`/`light`) are accepted via alias.
    heavy_chain: str = Field(validation_alias=AliasChoices("heavy_chain", "heavy"))
    light_chain: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("light_chain", "light")
    )
    temperature: float
    mutations: int
    seq_recovery: float


class AntiFoldGenerateResponseResultSequences(RequestModel):
    model_config = {
        "populate_by_name": True,  # Ensures alias names work
        "json_schema_extra": {
            "exclude_unset": True,  # Excludes unset (None) fields from the output
            "exclude_none": True,  # Ensures that None fields do not appear in JSON
        },
    }

    samples: Optional[list[AntiFoldGenerateResponseResultSamples]] = None


class AntiFoldGenerateResponseResult(ResponseModel):
    model_config = {
        "populate_by_name": True,  # Ensures alias names work
        "json_schema_extra": {
            "exclude_unset": True,  # Excludes unset (None) fields from the output
            "exclude_none": True,  # Ensures that None fields do not appear in JSON
        },
    }
    sequences: list[AntiFoldGenerateResponseResultSamples]
    logprobs: Optional[list[list[float]]] = None
    logits: Optional[list[list[float]]] = None
    pdb_posins: Optional[list[int]] = None
    pdb_chain: Optional[list[str]] = None
    pdb_res: Optional[list[str]] = None
    top_res: Optional[list[str]] = None
    perplexity: Optional[list[float]] = None
    vocab: Optional[list[str]] = None


class AntiFoldGenerateResponse(ResponseModel):
    results: list[AntiFoldGenerateResponseResult]


class AntiFoldLogProbResponseResult(ResponseModel):
    log_prob: float


class AntiFoldLogProbResponse(ResponseModel):
    results: list[AntiFoldLogProbResponseResult]


class AntiFoldScoreResponseResult(ResponseModel):
    model_config = {
        "populate_by_name": True,  # Ensures alias names work
        "json_schema_extra": {
            "exclude_unset": True,  # Excludes unset (None) fields from the output
            "exclude_none": True,  # Ensures that None fields do not appear in JSON
        },
    }
    global_score: float
    # Scored antibody chain sequences. Canonical output names; the upstream
    # AntiFold keys (`heavy`/`light`) are accepted via alias.
    heavy_chain: str = Field(validation_alias=AliasChoices("heavy_chain", "heavy"))
    light_chain: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("light_chain", "light")
    )


class AntiFoldScoreResponse(ResponseModel):
    results: list[AntiFoldScoreResponseResult]
