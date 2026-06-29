from functools import lru_cache
from typing import Annotated, Optional

from pydantic import BeforeValidator, Field, field_validator

from models.commons.data.validator import validate_dna_unambiguous
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)

### DNA-Chisel Model Parameters


class DnaChiselParams(ModelParams):
    weights_version = "v1"
    display_name = "DNA-Chisel"
    base_model_slug = "dna-chisel"
    log_identifier = "DNA-Chisel"
    batch_size = 1  # Process one sequence at a time


### DNA-Chisel Request


class DnaChiselFeatureOptions(EnhancedStringEnum):
    GC_CONTENT = "gc_content"
    CAI = "cai"
    HAIRPIN_SCORE = "hairpin_score"
    MELTING_TEMPERATURE = "melting_temperature"
    RESTRICTION_SITE_COUNT = "restriction_site_count"
    CODON_USAGE_ENTROPY = "codon_usage_entropy"
    RARE_CODON_FREQUENCY = "rare_codon_frequency"
    HOMOPOLYMER_RUN_LENGTH = "homopolymer_run_length"
    DINUCLEOTIDE_FREQUENCIES = "dinucleotide_frequencies"
    SEQUENCE_LENGTH = "sequence_length"
    TATA_BOX_COUNT = "tata_box_count"
    NON_UNIQUE_6MER_COUNT = "non_unique_6mer_count"
    IN_FRAME_STOP_CODON_COUNT = "in_frame_stop_codon_count"
    METHIONINE_FREQUENCY = "methionine_frequency"
    AT_SKEW = "at_skew"
    GC_SKEW = "gc_skew"
    NUCLEOTIDE_ENTROPY = "nucleotide_entropy"
    TANDEM_REPEAT_COUNT = "tandem_repeat_count"
    GC_CONTENT_STD_DEV = "gc_content_std_dev"
    KOZAK_SEQUENCE_STRENGTH = "kozak_sequence_strength"


class SupportedSpecies(EnhancedStringEnum):
    """Enum for species supported by `python_codon_tables`."""

    E_COLI = "e_coli"
    S_CEREVISIAE = "s_cerevisiae"
    H_SAPIENS = "h_sapiens"
    C_ELEGANS = "c_elegans"
    B_SUBTILIS = "b_subtilis"
    D_MELANOGASTER = "d_melanogaster"


@lru_cache(maxsize=1)
def list_supported_restriction_enzymes() -> list[str]:
    """Returns all restriction enzymes available in Biopython (cached)."""
    from Bio.Restriction import AllEnzymes

    return [enzyme.__name__ for enzyme in AllEnzymes]


class DnaChiselEncodeRequestParams(RequestModel):
    include: list[DnaChiselFeatureOptions] = Field(
        default_factory=lambda: list(DnaChiselFeatureOptions),
        description="Optional outputs to compute and include in the response.",
    )
    species: SupportedSpecies = Field(
        default=SupportedSpecies.E_COLI,
        description="Species name for codon-related features (e.g., CAI, rare codons).",
    )
    restriction_enzymes: Optional[list[str]] = Field(
        default=["EcoRI", "BsaI"],
        description="List of restriction enzymes for site-count feature. Set to None or an empty list to disable.",
    )

    @field_validator("restriction_enzymes", mode="before")
    def validate_restriction_enzymes(
        cls, enzymes: Optional[list[str]]
    ) -> Optional[list[str]]:
        """Ensures that only supported restriction enzymes are used."""
        if enzymes is None or enzymes == []:
            return enzymes  # Allow disabling enzyme checking

        valid_enzymes = set(list_supported_restriction_enzymes())
        invalid_enzymes = [e for e in enzymes if e not in valid_enzymes]

        if invalid_enzymes:
            raise ValueError(
                f"Invalid restriction enzymes: {invalid_enzymes}. "
                f"Valid options are: {valid_enzymes}"
            )

        return enzymes


class DnaChiselEncodeRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(validate_dna_unambiguous),
        Field(
            ..., min_length=1, description="A DNA sequence (A/C/G/T, uppercase only)."
        ),
    ]


class DnaChiselEncodeRequest(RequestModel):
    params: DnaChiselEncodeRequestParams = Field(
        default_factory=DnaChiselEncodeRequestParams,
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: Annotated[
        list[DnaChiselEncodeRequestItem],
        Field(
            min_length=1,
            max_length=DnaChiselParams.batch_size,
            description="Batch of inputs to process in a single request. Up to 1 sequence per request.",
        ),
    ]


### DNA-Chisel Response


class DnaChiselEncodeResponseResult(ResponseModel):
    gc_content: Optional[float] = Field(
        default=None,
        description="GC content of the sequence as a fraction (0–1).",
    )
    cai: Optional[float] = Field(
        default=None,
        description="Naive CAI approximation for the selected species: arithmetic mean of per-codon relative adaptiveness weights. Higher values indicate better codon optimization. Note: this is an arithmetic-mean approximation, not the classical geometric-mean CAI; values will differ from published CAI calculators.",
    )
    hairpin_score: Optional[float] = Field(
        default=None,
        description="Number of potential hairpin-forming regions detected in the sequence.",
    )
    melting_temperature: Optional[float] = Field(
        default=None,
        description="Computed melting temperature of the sequence in degrees Celsius.",
    )
    restriction_site_count: Optional[dict[str, int]] = Field(
        default=None,
        description="Number of occurrences of each restriction enzyme recognition site.",
    )
    codon_usage_entropy: Optional[float] = Field(
        default=None,
        description="Shannon entropy of the codon usage distribution; higher values indicate more uniform usage.",
    )
    rare_codon_frequency: Optional[float] = Field(
        default=None,
        description="Proportion of rare codons (relative usage < 0.1) in the sequence for the selected species.",
    )
    homopolymer_run_length: Optional[int] = Field(
        default=None,
        description="Maximum length of consecutive identical nucleotides (longest homopolymer run).",
    )
    dinucleotide_frequencies: Optional[dict[str, float]] = Field(
        default=None,
        description="Relative frequencies of each possible dinucleotide pair.",
    )
    sequence_length: Optional[int] = Field(
        default=None,
        description="Length of the input DNA sequence in nucleotides.",
    )
    tata_box_count: Optional[int] = Field(
        default=None,
        description="Number of TATA box motifs found in the sequence.",
    )
    non_unique_6mer_count: Optional[int] = Field(
        default=None,
        description="Number of distinct 6-mers that appear more than once in the sequence.",
    )
    in_frame_stop_codon_count: Optional[int] = Field(
        default=None,
        description="Number of in-frame stop codons; null if sequence length is not a multiple of 3.",
    )
    methionine_frequency: Optional[float] = Field(
        default=None,
        description="Frequency of methionine in the translated protein sequence; null if sequence length is not a multiple of 3.",
    )
    at_skew: Optional[float] = Field(
        default=None,
        description="AT skew of the sequence, computed as (A - T) / (A + T).",
    )
    gc_skew: Optional[float] = Field(
        default=None,
        description="GC skew of the sequence, computed as (G - C) / (G + C).",
    )
    nucleotide_entropy: Optional[float] = Field(
        default=None,
        description="Shannon entropy of the nucleotide composition.",
    )
    tandem_repeat_count: Optional[int] = Field(
        default=None,
        description="Number of tandem repeats (homopolymers) of length >= 3.",
    )
    gc_content_std_dev: Optional[float] = Field(
        default=None,
        description="Standard deviation of GC content computed in 50 bp sliding windows.",
    )
    kozak_sequence_strength: Optional[float] = Field(
        default=None,
        description="Binary score (1.0/0.0) for whether the sequence starts with the Kozak consensus (GCCRCCATGG).",
    )


class DnaChiselEncodeResponse(ResponseModel):
    results: list[DnaChiselEncodeResponseResult] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )
