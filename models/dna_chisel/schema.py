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
    params_version = "v1"
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


class DnaChiselPredictRequestParams(RequestModel):
    include: list[DnaChiselFeatureOptions] = Field(
        default_factory=lambda: list(DnaChiselFeatureOptions),
        description="List of features to include in the response.",
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


class DnaChiselPredictRequestItem(RequestModel):
    sequence: Annotated[
        str,
        BeforeValidator(validate_dna_unambiguous),
        Field(..., min_length=1),
    ]


class DnaChiselPredictRequest(RequestModel):
    params: DnaChiselPredictRequestParams = DnaChiselPredictRequestParams()
    items: Annotated[
        list[DnaChiselPredictRequestItem],
        Field(min_length=1, max_length=DnaChiselParams.batch_size),
    ]


### DNA-Chisel Response


class DnaChiselPredictResponseResult(ResponseModel):
    gc_content: Optional[float] = None
    cai: Optional[float] = None
    hairpin_score: Optional[float] = None
    melting_temperature: Optional[float] = None
    restriction_site_count: Optional[dict[str, int]] = None
    codon_usage_entropy: Optional[float] = None
    rare_codon_frequency: Optional[float] = None
    homopolymer_run_length: Optional[int] = None
    dinucleotide_frequencies: Optional[dict[str, float]] = None
    sequence_length: Optional[int] = None
    tata_box_count: Optional[int] = None
    non_unique_6mer_count: Optional[int] = None
    in_frame_stop_codon_count: Optional[int] = None
    methionine_frequency: Optional[float] = None
    at_skew: Optional[float] = None
    gc_skew: Optional[float] = None
    nucleotide_entropy: Optional[float] = None
    tandem_repeat_count: Optional[int] = None
    gc_content_std_dev: Optional[float] = None
    kozak_sequence_strength: Optional[float] = None


class DnaChiselPredictResponse(ResponseModel):
    results: list[DnaChiselPredictResponseResult]
