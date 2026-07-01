from typing import Annotated, Optional

from pydantic import BeforeValidator, Field, model_validator

from models.commons.data.structure_validator import validate_pdb
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)
from models.commons.util.config import max_pdb_str_len

### ThermoMPNN-D Params


class ThermoMPNNDParams(ModelParams):
    weights_version = "v1"
    display_name = "ThermoMPNN-D"
    base_model_slug = "thermompnn-d"
    log_identifier = "ThermoMPNN-D"
    batch_size = 1
    max_sequence_len = 1024


class ThermoMPNNDMode(EnhancedStringEnum):
    SINGLE = "single"
    ADDITIVE = "additive"
    EPISTATIC = "epistatic"


### ThermoMPNN-D Request


class ThermoMPNNDPredictParams(RequestModel):
    """Parameters for ThermoMPNN-D prediction"""

    mode: ThermoMPNNDMode = Field(
        default=ThermoMPNNDMode.SINGLE,
        description="Prediction mode: 'single' for individual mutation ddG, 'additive' for summed single-mutation effects, 'epistatic' for full pairwise interaction modeling.",
    )
    chain: Optional[str] = Field(
        default=None,
        description="Chain ID to use for prediction. If not specified, uses first chain in PDB.",
    )
    distance: float = Field(
        default=5.0,
        ge=0.0,
        description="Distance threshold (Angstroms) for filtering double mutations. Only mutations within this distance are considered.",
    )
    threshold: float = Field(
        default=-0.5,
        description="ddG threshold (kcal/mol) for filtering results. Only mutations with ddG <= threshold are returned. Set to a high value (e.g., 100) to return all mutations.",
    )


class ThermoMPNNDPredictRequestItem(RequestModel):
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
        description="List of mutations. For single mode: format 'WT{position}MUT' (e.g., 'A100V'). For double modes: format 'WT1{pos1}MUT1:WT2{pos2}MUT2' (e.g., 'A100V:B200L'). If not provided, a site-saturation mutagenesis (SSM) scan will be performed.",
    )

    @model_validator(mode="after")
    def validate_mutations(self) -> "ThermoMPNNDPredictRequestItem":  # noqa: C901
        """Validate mutation format if mutations are provided"""
        if self.mutations is None:
            return self  # No validation needed if mutations are not provided (SSM scan)

        alphabet = "ACDEFGHIKLMNPQRSTVWYX"

        for mut in self.mutations:
            if not mut:
                raise ValueError("Empty mutation string")

            # Check if it's a double mutation (contains ':')
            if ":" in mut:
                # Double mutation format: "WT1{pos1}MUT1:WT2{pos2}MUT2"
                parts = mut.split(":")
                if len(parts) != 2:
                    raise ValueError(
                        f"Invalid double mutation format: {mut}. Expected format: 'WT1{{pos1}}MUT1:WT2{{pos2}}MUT2' (e.g., 'A100V:B200L')"
                    )

                for part in parts:
                    if not part or len(part) < 3:
                        raise ValueError(
                            f"Invalid mutation part in double mutation: {part}"
                        )

                    wt = part[0]
                    mut_aa = part[-1]
                    try:
                        int(part[1:-1])  # Validate position is numeric
                    except ValueError as err:
                        raise ValueError(
                            f"Invalid mutation format: {part}. Position must be numeric."
                        ) from err

                    if wt not in alphabet:
                        raise ValueError(
                            f"Invalid wildtype amino acid: {wt}. Must be one of: {alphabet}"
                        )
                    if mut_aa not in alphabet:
                        raise ValueError(
                            f"Invalid mutation amino acid: {mut_aa}. Must be one of: {alphabet}"
                        )
            else:
                # Single mutation format: "WT{position}MUT"
                if len(mut) < 3:
                    raise ValueError(
                        f"Invalid mutation format: {mut}. Expected format: 'WT{{position}}MUT' (e.g., 'A100V')"
                    )

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

        return self


class ThermoMPNNDPredictRequest(RequestModel):
    params: ThermoMPNNDPredictParams = Field(
        description="Optional parameters controlling this action (defaults are used when omitted)."
    )
    items: Annotated[
        list[ThermoMPNNDPredictRequestItem],
        Field(
            min_length=1,
            max_length=1,
            description="Batch of inputs to process in a single request. Up to 1 PDB per request.",
        ),
    ]


### ThermoMPNN-D Response


class ThermoMPNNDPredictResponseItem(ResponseModel):
    """Response item for a mutation prediction (single or double)"""

    mutation: str = Field(
        ...,
        description="Mutation string in WT{pos}MUT format (single) or WT1{pos1}MUT1:WT2{pos2}MUT2 format (double).",
    )
    position: Optional[int] = Field(
        None, description="Residue position for single mutations (1-indexed)."
    )
    position1: Optional[int] = Field(
        None, description="First residue position for double mutations (1-indexed)."
    )
    position2: Optional[int] = Field(
        None, description="Second residue position for double mutations (1-indexed)."
    )
    wildtype: Optional[str] = Field(
        None, description="Wildtype amino acid for single mutations."
    )
    wildtype1: Optional[str] = Field(
        None, description="First wildtype amino acid for double mutations."
    )
    wildtype2: Optional[str] = Field(
        None, description="Second wildtype amino acid for double mutations."
    )
    mutation_aa: Optional[str] = Field(
        None, description="Mutant amino acid for single mutations."
    )
    mutation_aa1: Optional[str] = Field(
        None, description="First mutant amino acid for double mutations."
    )
    mutation_aa2: Optional[str] = Field(
        None, description="Second mutant amino acid for double mutations."
    )
    ddg: float = Field(
        ..., description="Predicted change in free energy (ddG) in kcal/mol."
    )
    distance: Optional[float] = Field(
        None,
        description="CA-CA distance (Angstroms) between the two mutation sites for double mutations.",
    )


class ThermoMPNNDPredictResponse(ResponseModel):
    results: list[ThermoMPNNDPredictResponseItem] = Field(
        description="Predicted ddG results, one entry per evaluated mutation (single or double)."
    )
