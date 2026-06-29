import re
from typing import Annotated, Optional

from pydantic import BeforeValidator, Field, field_validator, model_validator

from models.commons.data.structure_validator import validate_cif, validate_pdb
from models.commons.data.validator import (
    aa_unambiguous,
    validate_aa_unambiguous,
)
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import RequestModel, ResponseModel
from models.commons.util.config import max_pdb_str_len
from models.spurs._runtime import AMINO_ACID_ALPHABET
from models.spurs.util import extract_sequence_for_validation

### SPURS Model Parameters


class SpursParams(ModelParams):
    params_version = "v1"
    display_name = "SPURS"
    base_model_slug = "spurs"
    log_identifier = "SPURS"
    batch_size = 4
    max_sequence_len = 1024


_MUTATION_PATTERN = re.compile(r"^[A-Za-z](\d+)[A-Za-z]$")


def _normalize_mutation(value: str) -> str:
    normalized = value.strip().upper()
    match = _MUTATION_PATTERN.match(normalized)
    if not match:
        raise ValueError(
            "Mutation must follow the pattern <WT><position><Mutant>, e.g. M3L"
        )
    position = int(match.group(1))
    if position <= 0:
        raise ValueError("Mutation positions are 1-indexed and must be positive")
    return normalized


### SPURS Request


class SpursPredictRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(validate_aa_unambiguous),
        Field(
            ...,
            min_length=1,
            max_length=SpursParams.max_sequence_len,
            description="Protein sequence for SPURS prediction",
        ),
    ]
    pdb: Optional[Annotated[str, BeforeValidator(validate_pdb)]] = Field(
        default=None,
        min_length=1,
        max_length=max_pdb_str_len,
        description="Input structure in PDB format. Provide exactly one of pdb or cif.",
    )
    cif: Optional[Annotated[str, BeforeValidator(validate_cif)]] = Field(
        default=None,
        min_length=1,
        max_length=max_pdb_str_len,
        description="Input structure in mmCIF format. Provide exactly one of pdb or cif.",
    )
    chain_id: str = Field(
        "A",
        min_length=1,
        max_length=1,
        description=(
            "Single-letter chain identifier within the structure. Defaults to 'A'"
            " for single-chain proteins."
        ),
    )
    mutations: Optional[list[str]] = Field(
        default=None,
        description=(
            "Optional list of mutations (formatted '<WT><position><MT>' with 1-indexed"
            " positions) to evaluate. Omit this field to receive a full saturation"
            " mutagenesis matrix covering every single-residue substitution."
        ),
    )
    variant_sequence: Optional[
        Annotated[str, BeforeValidator(validate_aa_unambiguous)]
    ] = Field(
        default=None,
        min_length=1,
        max_length=SpursParams.max_sequence_len,
        description=(
            "Optional variant sequence for automatic mutation calculation. "
            "When provided with return_full_dms=False and mutations=None, "
            "the system will calculate mutations from the wild-type sequence "
            "(in 'sequence' field) to this variant sequence."
        ),
    )
    return_full_dms: bool = Field(
        default=True,
        description=(
            "When True and mutations is None, returns the full DMS matrix. "
            "When False and mutations is None, calculates mutations between the "
            "wild-type sequence (sequence field) and variant_sequence, treating "
            "them as manual mutations."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "sequence": "MKAAVDLKTF",
                    "pdb": "ATOM ...",
                    "chain_id": "A",
                    "mutations": ["K2L"],
                },
                {
                    "sequence": "MKAAVDLKTF",
                    "pdb": "ATOM ...",
                    "chain_id": "A",
                    "mutations": None,
                    "return_full_dms": True,
                },
                {
                    "sequence": "MKAAVDLKTF",
                    "pdb": "ATOM ...",
                    "chain_id": "A",
                    "variant_sequence": "MLAAVDLRTF",
                    "mutations": None,
                    "return_full_dms": False,
                },
            ]
        }
    }

    @field_validator("mutations", mode="before")
    def _normalize_mutation_list(cls, value):
        if value is None:
            return None
        if isinstance(value, list):
            if not value:
                raise ValueError(
                    "Mutations list cannot be empty; omit the field (set to null/None) "
                    "to request the full DMS matrix or auto-calculate from sequence difference."
                )
            return [_normalize_mutation(item) for item in value]
        raise ValueError(
            "Mutations, when provided, must be given as a list of mutation strings"
        )

    @model_validator(mode="after")
    def _validate_item(self):  # noqa: C901
        if not self.pdb and not self.cif:
            raise ValueError("Either 'pdb' or 'cif' content must be supplied")

        if self.chain_id.strip() == "":
            raise ValueError("chain_id cannot be blank")

        # Extract structure sequence for validation
        structure_text = self.pdb if self.pdb else self.cif
        structure_format = "pdb" if self.pdb else "cif"

        try:
            structure_sequence = extract_sequence_for_validation(
                structure_text, structure_format, self.chain_id
            )
        except ValueError as e:
            # Re-raise with more context
            raise ValueError(f"Structure validation failed: {str(e)}") from e
        except ImportError:
            # If biotite not available, skip structure-based validation
            structure_sequence = None

        # Validate sequence length compatibility with structure
        if structure_sequence and len(structure_sequence) != len(self.sequence):
            raise ValueError(
                f"Sequence length mismatch: structure has {len(structure_sequence)} "
                f"residues for chain '{self.chain_id}', but input sequence has "
                f"{len(self.sequence)} residues. The input sequence must match the "
                f"structure's sequence length exactly."
            )

        aa_lookup = aa_unambiguous

        # Validate explicit mutations if provided
        if self.mutations is not None:
            for mutation in self.mutations:
                wt, position_str, mt = mutation[0], mutation[1:-1], mutation[-1]
                position = int(position_str)

                if wt not in aa_lookup or mt not in aa_lookup:
                    raise ValueError(
                        f"Mutation '{mutation}' must use canonical amino acid codes"
                    )

                if position > len(self.sequence):
                    raise ValueError(
                        f"Mutation '{mutation}' position {position} exceeds sequence "
                        f"length {len(self.sequence)}"
                    )

                # Validate against input sequence
                input_residue = self.sequence[position - 1]
                if input_residue != wt:
                    raise ValueError(
                        f"Mutation '{mutation}' specifies wild-type residue '{wt}' at "
                        f"position {position}, but input sequence has '{input_residue}'"
                    )

                # Validate against structure sequence if available
                if structure_sequence:
                    if position > len(structure_sequence):
                        raise ValueError(
                            f"Mutation '{mutation}' position {position} exceeds structure "
                            f"sequence length {len(structure_sequence)}"
                        )

                    structure_residue = structure_sequence[position - 1]

                    # Check if the wild-type in mutation matches the structure
                    if structure_residue != wt:
                        raise ValueError(
                            f"Mutation '{mutation}' specifies wild-type residue '{wt}' at "
                            f"position {position}, but the structure (chain '{self.chain_id}') "
                            f"has residue '{structure_residue}' at that position. The mutation "
                            f"must match the structure's actual sequence."
                        )

        # Validate variant_sequence if provided
        if self.variant_sequence:
            if self.mutations is not None:
                raise ValueError(
                    "Cannot specify both 'variant_sequence' and 'mutations'. "
                    "Use variant_sequence for automatic calculation or mutations for manual specification."
                )

            if self.return_full_dms:
                raise ValueError(
                    "variant_sequence requires return_full_dms=False. "
                    "Set return_full_dms=False to enable automatic mutation calculation."
                )

            # Validate variant sequence length matches
            if len(self.variant_sequence) != len(self.sequence):
                raise ValueError(
                    f"Variant sequence length ({len(self.variant_sequence)}) must match "
                    f"wild-type sequence length ({len(self.sequence)})"
                )

            # Validate variant matches structure length
            if structure_sequence and len(self.variant_sequence) != len(
                structure_sequence
            ):
                raise ValueError(
                    f"Variant sequence length ({len(self.variant_sequence)}) must match "
                    f"structure sequence length ({len(structure_sequence)})"
                )

        return self


class SpursPredictRequest(RequestModel):
    items: Annotated[
        list[SpursPredictRequestItem],
        Field(
            min_length=1,
            max_length=SpursParams.batch_size,
            description="List of protein sequences and mutations for SPURS prediction",
        ),
    ]


### SPURS Response


class SpursDDGMatrix(ResponseModel):
    values: list[list[float]] = Field(
        ...,
        description=(
            "ΔΔG matrix in kcal/mol with shape (sequence_length, 20). Rows follow"
            " the input sequence order; columns follow `amino_acid_axis`."
        ),
    )
    residue_axis: list[str] = Field(
        ...,
        description=(
            "Residue labels for each matrix row (wild-type amino acid per sequence"
            " position)."
        ),
    )
    amino_acid_axis: list[str] = Field(
        default_factory=lambda: list(AMINO_ACID_ALPHABET),
        description=(
            "Order of amino acids for matrix columns (canonical 20-letter alphabet)."
        ),
    )


class SpursPredictResponseResult(ResponseModel):
    mutations: Optional[list[str]] = Field(
        default=None,
        description=(
            "Specific mutations evaluated. Null indicates the response includes a full"
            " ΔΔG matrix covering every single-residue substitution."
        ),
    )
    ddG: Optional[float] = Field(
        default=None,
        description=(
            "Predicted ΔΔG in kcal/mol for the requested mutation set. Present when"
            " one or more explicit mutations were supplied."
        ),
    )
    ddG_contributions: Optional[dict[str, float]] = Field(
        default=None,
        description=(
            "Per-mutation ΔΔG contributions (kcal/mol) for multi-mutation requests."
        ),
    )
    ddG_matrix: Optional[SpursDDGMatrix] = Field(
        default=None,
        description=(
            "Complete single-mutation ΔΔG matrix. Provided when mutations are omitted"
            " in the request."
        ),
    )


class SpursPredictResponse(ResponseModel):
    results: list[SpursPredictResponseResult] = Field(
        ...,
        description=(
            "SPURS prediction results. Each entry corresponds to one request item"
            " and includes either per-mutation ΔΔG values or a full saturation"
            " mutagenesis matrix."
        ),
    )
