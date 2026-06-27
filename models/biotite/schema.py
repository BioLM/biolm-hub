from typing import Annotated

from pydantic import BeforeValidator, Field

from models.commons.data.structure_validator import validate_pdb
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    RequestModel,
    ResponseModel,
)

### Biotite Params


class BiotiteParams(ModelParams):
    params_version = "v1"
    display_name = "Biotite"
    base_model_slug = "biotite"
    log_identifier = "BIOTITE"
    batch_size = 8
    max_sequence_len = 2048


### Biotite Request


class BiotiteExtractChainsRequestParams(RequestModel):
    """Optional parameters for chain extraction."""

    pass


class BiotiteExtractChainsRequestItem(RequestModel):
    pdb_string: Annotated[
        str,
        BeforeValidator(validate_pdb),
        Field(..., min_length=1, description="PDB structure as string"),
    ]
    chain_ids: Annotated[
        list[str],
        Field(
            ..., min_length=1, max_length=10, description="List of chain IDs to extract"
        ),
    ]


class BiotiteExtractChainsRequest(RequestModel):
    params: BiotiteExtractChainsRequestParams | None = None
    items: Annotated[
        list[BiotiteExtractChainsRequestItem],
        Field(min_length=1, max_length=BiotiteParams.batch_size),
    ]


class BiotiteRMSDRequestParams(RequestModel):
    """Optional parameters for RMSD computation."""

    pass


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
    chain_ids: Annotated[
        dict[str, list[str]],
        Field(
            ...,
            description="Mapping of PDB to chain IDs: {'a': [chain_ids_for_pdb_a], 'b': [chain_ids_for_pdb_b]}",
        ),
    ]


class BiotiteRMSDRequest(RequestModel):
    params: BiotiteRMSDRequestParams | None = None
    items: Annotated[
        list[BiotiteRMSDRequestItem],
        Field(min_length=1, max_length=BiotiteParams.batch_size),
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
    results: list[BiotiteExtractChainsResponseResult]


class BiotiteRMSDResponseResult(ResponseModel):
    """Result of RMSD computation between two structures."""

    rmsd: float = Field(..., description="Root mean square deviation in Angstroms")


class BiotiteRMSDResponse(ResponseModel):
    results: list[BiotiteRMSDResponseResult]
