from typing import Annotated

from pydantic import AliasChoices, BeforeValidator, Field, model_validator

from models.commons.data.structure_validator import validate_pdb
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    RequestModel,
    ResponseModel,
)

### Biotite Params


class BiotiteParams(ModelParams):
    weights_version = "v1"
    display_name = "Biotite"
    base_model_slug = "biotite"
    log_identifier = "BIOTITE"
    batch_size = 8


### Biotite Request


class BiotiteExtractChainsRequestItem(RequestModel):
    pdb: Annotated[
        str,
        BeforeValidator(validate_pdb),
        Field(
            ...,
            min_length=1,
            description="PDB structure as string",
            validation_alias=AliasChoices("pdb", "pdb_string"),
        ),
    ]
    chain_ids: Annotated[
        list[str],
        Field(
            ..., min_length=1, max_length=10, description="List of chain IDs to extract"
        ),
    ]


class BiotiteExtractChainsRequest(RequestModel):
    items: Annotated[
        list[BiotiteExtractChainsRequestItem],
        Field(
            min_length=1,
            max_length=BiotiteParams.batch_size,
            description="Batch of inputs to process in a single request. Up to 8 structures per request.",
        ),
    ]


class BiotiteRMSDRequestItem(RequestModel):
    pdb_a: Annotated[
        str,
        BeforeValidator(validate_pdb),
        Field(..., min_length=1, description="First PDB structure as string"),
    ]
    pdb_b: Annotated[
        str,
        BeforeValidator(validate_pdb),
        Field(..., min_length=1, description="Second PDB structure as string"),
    ]
    chain_a: Annotated[
        list[str],
        Field(
            ...,
            min_length=1,
            description=(
                "Chain IDs from pdb_a for RMSD comparison. "
                "Must have the same length as chain_b."
            ),
        ),
    ]
    chain_b: Annotated[
        list[str],
        Field(
            ...,
            min_length=1,
            description=(
                "Chain IDs from pdb_b for RMSD comparison. "
                "Must have the same length as chain_a."
            ),
        ),
    ]

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_chain_ids(cls, values: object) -> object:
        """Accept legacy chain_ids dict format: {'a': [...], 'b': [...]}.

        Callers may still send ``chain_ids={"a": [...], "b": [...]}``; this
        validator converts that form to the canonical ``chain_a``/``chain_b``
        fields so existing integrations keep working.
        """
        if isinstance(values, dict) and "chain_ids" in values:
            chain_ids = values.pop("chain_ids")
            if isinstance(chain_ids, dict) and "chain_a" not in values:
                if "a" in chain_ids:
                    values["chain_a"] = chain_ids["a"]
                if "b" in chain_ids:
                    values["chain_b"] = chain_ids["b"]
        return values

    @model_validator(mode="after")
    def _validate_chain_lengths(self) -> "BiotiteRMSDRequestItem":
        if len(self.chain_a) != len(self.chain_b):
            raise ValueError(
                f"chain_a and chain_b must have the same length: "
                f"got {len(self.chain_a)} vs {len(self.chain_b)}"
            )
        return self


class BiotiteRMSDRequest(RequestModel):
    items: Annotated[
        list[BiotiteRMSDRequestItem],
        Field(
            min_length=1,
            max_length=BiotiteParams.batch_size,
            description="Batch of inputs to process in a single request. Up to 8 structure pairs per request.",
        ),
    ]


### Biotite Response


class BiotiteExtractChainsResponseResult(ResponseModel):
    """Result of chain extraction from PDB structure."""

    chain_sequences: dict[str, str] = Field(
        ..., description="Mapping of chain ID to amino acid sequence"
    )
    chain_pdb_strings: dict[str, str] = Field(
        ..., description="Mapping of chain ID to PDB structure string"
    )


class BiotiteExtractChainsResponse(ResponseModel):
    results: list[BiotiteExtractChainsResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )


class BiotiteRMSDResponseResult(ResponseModel):
    """Result of RMSD computation between two structures."""

    rmsd: float = Field(..., description="Root mean square deviation in Angstroms")


class BiotiteRMSDResponse(ResponseModel):
    results: list[BiotiteRMSDResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )
