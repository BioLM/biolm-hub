from typing import Annotated, Optional

from pydantic import Field, ValidationInfo, field_validator

from models.commons.data.validator import (
    aa_unambiguous,
    dna_unambiguous,
    rna_unambiguous,
    validate_smiles,
)
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

### Chai-1 Params


class Chai1Params(ModelParams):
    params_version = "v1"
    display_name = "Chai-1"
    base_model_slug = "chai1"
    log_identifier = "Chai1"
    batch_size = 1  # Note: Keep batch_size fixed to 1
    max_sequence_len = 1024  # Max length for protein sequences
    max_rna_dna_len = 3 * max_sequence_len  # Max length for RNA/DNA sequences
    max_ligand_len = max_sequence_len // 8  # Max length for ligand sequences
    max_fasta_entries = 5  # Max number of FASTA entries


class Chai1EntityType(EnhancedStringEnum):
    PROTEIN = "protein"
    DNA = "DNA"
    RNA = "RNA"
    LIGAND = "ligand"
    POLYMER_HYBRID = "polymer_hybrid"
    WATER = "water"
    UNKNOWN = "unknown"


class Chai1AlignmentDatabase(EnhancedStringEnum):
    MGNIFY = "mgnify"
    SMALL_BFD = "small_bfd"
    UNIREF90 = "uniref90"


### Chai-1 Entity


class Chai1Molecule(RequestModel):
    name: str = Field(
        description="Human-readable name identifying this molecule within the complex (used in FASTA headers and MSA labels)."
    )
    type: Chai1EntityType = Field(
        description="Molecule type (protein, DNA, RNA, ligand, polymer_hybrid, water, or unknown)."
    )
    sequence: Optional[str] = Field(
        default=None,
        description="Amino-acid, nucleotide (DNA/RNA), or SMILES sequence for the molecule; validated against the declared entity type.",
    )
    smiles: Optional[str] = Field(
        default=None,
        description="Ligand structure as a SMILES string.",
    )
    alignment: Optional[dict[Chai1AlignmentDatabase, str]] = Field(
        default=None,
        description="Pre-computed MSA alignments for this protein molecule; keys are database names, values are A3M-format strings.",
    )

    @field_validator("sequence")
    def validate_sequence(cls, v, info: ValidationInfo):  # noqa: C901
        # FIXME(noqa: C901): Refactor to reduce complexity below the linter's threshold.

        if v is None:
            return v

        entity_type = info.data.get("type")
        if entity_type == Chai1EntityType.PROTEIN:
            if not all(residue in aa_unambiguous for residue in v.upper()):
                raise ValueError("Protein sequence contains invalid residues")
            if len(v) > Chai1Params.max_sequence_len:
                raise ValueError(
                    f"Protein sequence exceeds maximum length of {Chai1Params.max_sequence_len}"
                )
        elif entity_type in {Chai1EntityType.DNA, Chai1EntityType.RNA}:
            if len(v) > Chai1Params.max_rna_dna_len:
                raise ValueError(
                    f"{entity_type.value} sequence exceeds maximum length of {Chai1Params.max_rna_dna_len}"
                )
            if entity_type == Chai1EntityType.DNA and not all(
                residue in dna_unambiguous for residue in v.upper()
            ):
                raise ValueError("DNA sequence contains invalid bases")
            if entity_type == Chai1EntityType.RNA and not all(
                residue in rna_unambiguous for residue in v.upper()
            ):
                raise ValueError("RNA sequence contains invalid bases")
        elif entity_type == Chai1EntityType.LIGAND:
            if len(v) > Chai1Params.max_ligand_len:
                raise ValueError(
                    f"Ligand sequence exceeds maximum length of {Chai1Params.max_ligand_len}"
                )
            v = validate_smiles(v)
        return v

    @field_validator("smiles")
    def validate_smiles_field(cls, v, info: ValidationInfo):
        """Validate the explicit smiles field when provided."""
        if v is not None:
            if len(v) > Chai1Params.max_ligand_len:
                raise ValueError(
                    f"Ligand SMILES exceeds maximum length of {Chai1Params.max_ligand_len}"
                )
            v = validate_smiles(v)
        return v

    @field_validator("alignment")
    def validate_alignment(cls, v, info: ValidationInfo):
        if v is not None:
            entity_type = info.data.get("type")
            if entity_type != Chai1EntityType.PROTEIN:
                raise ValueError("Alignment can only be set for protein molecules")
        return v


### Chai-1 Predict Request


class Chai1ScoreOptions(EnhancedStringEnum):
    PAE = "pae"
    PLDDT = "plddt"


class Chai1PredictRequestParams(RequestModel):
    num_trunk_recycles: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Number of trunk recycling iterations; more recycles improve accuracy at the cost of inference time.",
    )
    num_diffusion_timesteps: int = Field(
        default=200,
        ge=50,
        le=200,
        description="Number of diffusion denoising timesteps; higher values improve structure quality at the cost of inference time.",
    )
    num_diffn_samples: int = Field(
        default=1,
        ge=1,
        le=5,
        description="Number of candidate structures to generate per input complex (1–5); more samples increase output diversity.",
    )
    use_esm_embeddings: bool = Field(
        default=True,
        description="Whether to use ESM protein language model embeddings to enrich sequence representations.",
    )
    seed: int = Field(
        default=42,
        description="Random seed for reproducible sampling.",
    )
    include: list[Chai1ScoreOptions] = Field(
        default_factory=list,
        description="Confidence-score outputs to include in the response. Currently disabled — pae/plddt are not returned due to large payload size. Pass an empty list or omit this field.",
    )

    @field_validator("include")
    def force_empty_include(cls, v):
        if v:
            raise ValueError(
                "pae/plddt scoring outputs are currently disabled. "
                "Omit the 'include' parameter or pass an empty list."
            )
        return []


class Chai1PredictRequestInput(RequestModel):
    molecules: list[Chai1Molecule] = Field(
        description="List of molecules forming the complex to predict (up to 5 entities per request)."
    )

    @field_validator("molecules")
    def validate_molecules(cls, v):
        if not v:
            raise ValueError("Molecules must not be empty.")
        if len(v) > Chai1Params.max_fasta_entries:
            raise ValueError(
                f"Number of molecules exceeds maximum of {Chai1Params.max_fasta_entries}"
            )
        return v


class Chai1PredictRequest(RequestModel):
    params: Chai1PredictRequestParams = Field(
        default_factory=Chai1PredictRequestParams,
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: Annotated[
        list[Chai1PredictRequestInput],
        Field(
            min_length=1,
            max_length=Chai1Params.batch_size,
            description="Batch of inputs to process in a single request.",
        ),
    ]


### Chai-1 Predict Response


class Chai1PredictResponseResult(ResponseModel):
    model_config = {
        "populate_by_name": True,  # Ensures alias names work as expected
        "json_schema_extra": {
            "exclude_unset": True,  # Excludes unset (None) fields from the output
            "exclude_none": True,  # Ensures that None fields do not appear in JSON
        },
    }

    cif: str = Field(description="Predicted structure in mmCIF format.")
    pae: Optional[list[list[float]]] = Field(
        default=None,
        description="Predicted aligned error (PAE) matrix, in Ångströms.",
    )
    plddt: Optional[list[float]] = Field(
        default=None,
        description="Per-residue pLDDT confidence score (0–100; higher is more confident).",
    )


class Chai1PredictResponse(ResponseModel):
    results: list[list[Chai1PredictResponseResult]] = Field(
        description="Per-input results, returned in the same order as the request items."
    )  # multiple samples in list must correspond to idx of input items
