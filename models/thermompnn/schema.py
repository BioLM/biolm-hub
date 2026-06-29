from typing import Annotated, Optional

from pydantic import BeforeValidator, Field, model_validator

from models.commons.data.structure_validator import validate_pdb
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    RequestModel,
    ResponseModel,
)
from models.commons.util.config import max_pdb_str_len

### ThermoMPNN Params


class ThermoMPNNParams(ModelParams):
    params_version = "v1"
    display_name = "ThermoMPNN"
    base_model_slug = "thermompnn"
    log_identifier = "ThermoMPNN"
    batch_size = 1
    max_sequence_len = 1024


### ThermoMPNN Request


class ThermoMPNNPredictParams(RequestModel):
    """Parameters for ThermoMPNN prediction"""

    chain: Optional[str] = Field(
        default=None,
        description="Chain ID to use for prediction. If not specified, uses first chain in PDB.",
    )


class ThermoMPNNPredictRequestItem(RequestModel):
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
    mutations: Optional[list[str]] = Field(
        default=None,
        description="Optional list of mutations in format 'WT{position}MUT' (e.g., 'A100V' for Ala->Val at position 100). Position is 1-indexed within the selected chain's modeled sequence (not PDB residue numbers). If not provided, performs site-saturation mutagenesis (SSM) scan for all positions.",
    )

    @model_validator(mode="after")
    def validate_mutations(cls, instance):
        """Validate mutation format if mutations are provided"""
        if instance.mutations is None:
            return instance  # SSM scan will be performed

        alphabet = "ACDEFGHIKLMNPQRSTVWYX"
        for mut in instance.mutations:
            if not mut or len(mut) < 3:
                raise ValueError(
                    f"Invalid mutation format: {mut}. Expected format: 'WT{{position}}MUT' (e.g., 'A100V')"
                )

            # Extract wildtype, position, and mutation
            wt = mut[0]
            mut_aa = mut[-1]
            try:
                int(mut[1:-1])  # Validate position is numeric
            except ValueError as err:
                raise ValueError(
                    f"Invalid mutation format: {mut}. Position must be numeric."
                ) from err

            if wt not in alphabet:
                raise ValueError(
                    f"Invalid wildtype amino acid: {wt}. Must be one of: {alphabet}"
                )
            if mut_aa not in alphabet:
                raise ValueError(
                    f"Invalid mutation amino acid: {mut_aa}. Must be one of: {alphabet}"
                )

        return instance


class ThermoMPNNPredictRequest(RequestModel):
    params: ThermoMPNNPredictParams = Field(
        ...,
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: Annotated[
        list[ThermoMPNNPredictRequestItem],
        Field(
            min_length=1,
            max_length=ThermoMPNNParams.batch_size,
            description="Batch of inputs to process in a single request. Exactly 1 PDB structure per request.",
        ),
    ]


### ThermoMPNN Response


class ThermoMPNNPredictResponseItem(ResponseModel):
    """Response item for a single mutation prediction"""

    mutation: str = Field(..., description="Mutation in format 'WT{position}MUT'.")
    position: int = Field(
        ...,
        description="Residue position (1-indexed within the selected chain's modeled sequence, not PDB residue numbers).",
    )
    wildtype: str = Field(..., description="Wildtype amino acid.")
    mutation_aa: str = Field(..., description="Mutant amino acid.")
    ddg: float = Field(
        ..., description="Predicted change in free energy (ddG) in kcal/mol."
    )


class ThermoMPNNPredictResponse(ResponseModel):
    results: list[ThermoMPNNPredictResponseItem] = Field(
        ...,
        description="Per-input results, returned in the same order as the request items.",
    )
