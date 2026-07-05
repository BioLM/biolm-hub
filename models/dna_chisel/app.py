import itertools

import modal
import numpy as np

from models.commons.core.decorator import modal_endpoint
from models.commons.core.logging import get_logger
from models.commons.modal.source import setup_source_layer
from models.commons.model.base import ModelMixinSnap
from models.commons.model.config import biolm_model_class
from models.commons.util.config import (
    common_requirements,
    runtime_secrets,
)
from models.dna_chisel.config import MODEL_FAMILY
from models.dna_chisel.schema import (
    DnaChiselEncodeRequest,
    DnaChiselEncodeResponse,
    DnaChiselEncodeResponseResult,
    DnaChiselFeatureOptions,
    DnaChiselParams,
)

logger = get_logger(__name__)

# Build Modal container image
image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("procps")  # Critical for computing container uptime
    .uv_pip_install(common_requirements)
    .uv_pip_install(
        "dnachisel==3.2.13",
        "python-codon-tables==0.1.13",
        "primer3-py==2.0.3",
        "numpy==1.26.4",
        "scipy==1.11.4",
    )
)
# Finally, add all model files
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)


# Define the app using unified config
app_name, modal_resource_spec = MODEL_FAMILY.get_app_config()
logger.info("App name: %s", app_name)
app = modal.App(app_name, image=image)


@app.cls(
    image=image,
    secrets=runtime_secrets(),
    enable_memory_snapshot=True,
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class DnaChiselModel(ModelMixinSnap):
    app_username: str = modal.parameter(default="default_user")

    @modal.enter(snap=True)
    def load_model(self) -> None:

        import dnachisel
        import primer3

        # Module __dict__ used to look up enzyme classes by name; dynamic, not typed.
        from Bio.Restriction import __dict__ as restr_dict  # type: ignore[attr-defined]
        from python_codon_tables import get_codons_table
        from scipy.stats import entropy as scipy_entropy

        logger.info(
            "Loading %s model on CPU for memory snapshot...",
            DnaChiselParams.display_name,
        )

        # Save modules and key functions as attributes for later use.
        self.dnachisel = dnachisel
        self.primer3 = primer3
        self.itertools = itertools
        self.np = np

        self.get_codons_table = get_codons_table
        self.entropy = scipy_entropy

        # Store dnachisel functionality.
        self.AvoidHairpins = dnachisel.builtin_specifications.AvoidHairpins
        self.DnaNotationPattern = dnachisel.DnaNotationPattern
        self.DnaOptimizationProblem = dnachisel.DnaOptimizationProblem
        self.SequencePattern = dnachisel.SequencePattern
        self.reverse_complement = dnachisel.reverse_complement

        # Biotools functions
        self.gc_content = dnachisel.biotools.gc_content
        self.translate = dnachisel.biotools.translate

        # For melting temperature, use primer3's calc_tm function.
        self.tm = primer3.calc_tm

        # Import and store the restriction enzymes dictionary for later use.
        self._restr_dict = restr_dict

    @modal.enter(snap=False)
    def setup_model(self) -> None:
        logger.info(
            "%s model ready for inference from memory snapshot!",
            DnaChiselParams.display_name,
        )

    # 1) GC Content
    def compute_gc_content(self, sequence: str) -> float:
        """Compute the global GC content of the sequence."""
        return float(self.gc_content(sequence))

    # 2) CAI
    def compute_cai(self, sequence: str, species: str) -> float:
        """
        Compute a naive Codon Adaptation Index (CAI).
        For each codon, calculate its relative weight by dividing its frequency
        by the frequency of the most common synonymous codon, and return the average.
        """
        table = self.get_codons_table(species)
        codon_weights = {}
        for aa, freq_dict in table.items():
            if len(aa) == 1:  # Skip non-amino acid entries (e.g. stop codons)
                max_freq = max(freq_dict.values()) if freq_dict else 1.0
                for codon, f in freq_dict.items():
                    codon_weights[codon] = f / max_freq

        codons = [
            sequence[i : i + 3]
            for i in range(0, len(sequence), 3)
            if len(sequence[i : i + 3]) == 3
        ]
        weights = [codon_weights.get(cod, 0.0) for cod in codons]
        return float(self.np.mean(weights)) if weights else 0.0

    # 3) Hairpin Score
    def compute_hairpin_score(self, sequence: str) -> float:
        """
        Compute the hairpin score using the AvoidHairpins specification.
        The specification's score is defined as negative of the hairpin count;
        we return the positive hairpin count.
        """
        spec = self.AvoidHairpins(
            stem_size=20, hairpin_window=200, location=(0, len(sequence))
        )
        prob = self.DnaOptimizationProblem(sequence=sequence, constraints=[spec])
        evaluation = spec.evaluate(prob)
        return float(-evaluation.score)

    # 4) Melting Temperature
    def compute_melting_temperature(self, sequence: str) -> float:
        """Compute the melting temperature using primer3.calcTm."""
        return float(self.tm(sequence))

    # 5) Restriction Site Count
    def compute_restriction_site_count(
        self, sequence: str, enzymes: list[str]
    ) -> dict[str, int]:
        """
        Count occurrences of each enzyme's recognition pattern in the sequence.
        Each enzyme string is first converted to its recognition sequence.
        """
        result: dict[str, int] = {}
        for enzyme in enzymes:
            enzyme_obj = self._restr_dict.get(enzyme)
            if enzyme_obj is not None and hasattr(enzyme_obj, "site"):
                rec_site = enzyme_obj.site  # e.g., EcoRI.site returns "GAATTC"
            else:
                rec_site = enzyme  # assume already a valid pattern
            pattern = self.DnaNotationPattern(rec_site)
            matches = pattern.find_matches(sequence)
            result[enzyme] = int(len(matches))
        return result

    # 6) Codon Usage Entropy
    def compute_codon_usage_entropy(self, sequence: str) -> float:
        """
        Compute the Shannon entropy of codon usage in the sequence.
        """
        codons = [
            sequence[i : i + 3]
            for i in range(0, len(sequence), 3)
            if len(sequence[i : i + 3]) == 3
        ]
        if not codons:
            return 0.0
        counts: dict[str, int] = {}
        for c in codons:
            counts[c] = counts.get(c, 0) + 1
        freqs = [val / len(codons) for val in counts.values()]
        return float(self.entropy(freqs, base=2))

    # 7) Rare Codon Frequency
    def compute_rare_codon_frequency(self, sequence: str, species: str) -> float:
        """
        Compute the fraction of codons considered 'rare' (relative usage < 0.1)
        for the specified species.
        """
        table = self.get_codons_table(species)
        codon_weights = {}
        for aa, freq_dict in table.items():
            if len(aa) == 1:
                max_freq = max(freq_dict.values()) if freq_dict else 1.0
                for codon, f in freq_dict.items():
                    codon_weights[codon] = f / max_freq

        codons = [
            sequence[i : i + 3]
            for i in range(0, len(sequence), 3)
            if len(sequence[i : i + 3]) == 3
        ]
        if not codons:
            return 0.0
        threshold = 0.1
        rare_count = sum(1 for c in codons if codon_weights.get(c, 1.0) < threshold)
        return float(rare_count) / float(len(codons))

    # 8) Homopolymer Run
    def compute_homopolymer_run_length(self, sequence: str) -> int:
        """Compute the maximum run length of a single nucleotide in the sequence."""
        if not sequence:
            return 0
        max_run = 1
        current_run = 1
        current_nuc = sequence[0]
        for nuc in sequence[1:]:
            if nuc == current_nuc:
                current_run += 1
                if current_run > max_run:
                    max_run = current_run
            else:
                current_nuc = nuc
                current_run = 1
        return int(max_run)

    # 9) Dinucleotide Frequencies
    def compute_dinucleotide_frequencies(self, sequence: str) -> dict[str, float]:
        """
        Compute the frequency of each dinucleotide (2-mer) in the sequence.
        """
        total_len = len(sequence) - 1
        if total_len <= 0:
            return {
                d: 0.0
                for d in ["".join(x) for x in self.itertools.product("ACGT", repeat=2)]
            }
        possible_dinucs = ["".join(x) for x in self.itertools.product("ACGT", repeat=2)]
        counts = {d: 0 for d in possible_dinucs}
        for i in range(total_len):
            dinuc = sequence[i : i + 2]
            if dinuc in counts:
                counts[dinuc] += 1
        return {k: float(v) / float(total_len) for k, v in counts.items()}

    # 10) Sequence Length
    def compute_sequence_length(self, sequence: str) -> int:
        """Return the length of the sequence."""
        return int(len(sequence))

    # 11) TATA Box Count
    def compute_tata_box_count(self, sequence: str) -> int:
        """Count the occurrences of the 'TATA' motif in the sequence."""
        pattern = self.DnaNotationPattern("TATA")
        matches = pattern.find_matches(sequence)
        return int(len(matches))

    # 12) Non-unique 6-mer Count
    def compute_non_unique_6mer_count(self, sequence: str) -> int:
        """
        Count the number of distinct 6-mers in the sequence that appear more than once.
        """
        if len(sequence) < 6:
            return 0
        kmers = [sequence[i : i + 6] for i in range(len(sequence) - 5)]
        counts: dict[str, int] = {}
        for k in kmers:
            counts[k] = counts.get(k, 0) + 1
        return int(sum(1 for c in counts.values() if c > 1))

    # 13) In-frame Stop Codon Count
    def compute_in_frame_stop_codon_count(self, sequence: str) -> int | None:
        """
        Count the number of stop codons in the in-frame translation.
        Returns None if the sequence length is not a multiple of 3.
        """
        if len(sequence) % 3 != 0:
            return None
        translation = self.translate(sequence)
        return int(translation.count("*"))

    # 14) Methionine Frequency
    def compute_methionine_frequency(self, sequence: str) -> float | None:
        """
        Compute the frequency of the Methionine ('M') amino acid in the translated sequence.
        Returns None if the sequence length is not a multiple of 3.
        """
        if len(sequence) % 3 != 0:
            return None
        translation = self.translate(sequence)
        if not translation:
            return 0.0
        meth_count = translation.count("M")
        return float(meth_count) / float(len(translation))

    # 15) AT Skew
    def compute_at_skew(self, sequence: str) -> float:
        """Compute the AT skew as (A - T) / (A + T)."""
        a_count = sequence.count("A")
        t_count = sequence.count("T")
        denom = a_count + t_count
        if denom == 0:
            return 0.0
        return float(a_count - t_count) / float(denom)

    # 16) GC Skew
    def compute_gc_skew(self, sequence: str) -> float:
        """Compute the GC skew as (G - C) / (G + C)."""
        g_count = sequence.count("G")
        c_count = sequence.count("C")
        denom = g_count + c_count
        if denom == 0:
            return 0.0
        return float(g_count - c_count) / float(denom)

    # 17) Nucleotide Entropy
    def compute_nucleotide_entropy(self, sequence: str) -> float:
        """
        Compute the Shannon entropy of the nucleotide composition of the sequence.
        """
        if not sequence:
            return 0.0
        total_len = len(sequence)
        a = sequence.count("A")
        c = sequence.count("C")
        g = sequence.count("G")
        t = sequence.count("T")
        freqs = [a / total_len, c / total_len, g / total_len, t / total_len]
        # Filter out zeros to avoid math domain errors
        freqs = [f for f in freqs if f > 0]
        return float(self.entropy(freqs, base=2)) if freqs else 0.0

    # 18) Tandem Repeat Count (≥3bp)
    def compute_tandem_repeat_count(self, sequence: str) -> int:
        """
        Count the number of tandem (homopolymer) repeats of length at least 3.
        """
        if len(sequence) < 3:
            return 0
        repeat_starts = []
        i = 0
        while i < len(sequence) - 2:
            if sequence[i] == sequence[i + 1] == sequence[i + 2]:
                repeat_starts.append(i)
                # Skip to the end of the homopolymer run
                while i < len(sequence) - 1 and sequence[i] == sequence[i + 1]:
                    i += 1
            i += 1
        return int(len(repeat_starts))

    # 19) GC Content Standard Deviation (in 50bp windows)
    def compute_gc_content_std_dev(self, sequence: str, window: int = 50) -> float:
        """
        Compute the standard deviation of the GC content in sliding windows of the given size.
        """
        if len(sequence) < window:
            return 0.0
        values = []
        for i in range(len(sequence) - window + 1):
            subseq = sequence[i : i + window]
            values.append(self.gc_content(subseq))
        return float(self.np.std(values)) if values else 0.0

    # 20) Kozak Sequence Strength
    def compute_kozak_sequence_strength(self, sequence: str) -> float:
        """
        Evaluate the Kozak sequence strength in a naive way:
        Return 1.0 if the sequence starts with the consensus "GCCRCCATGG", else 0.0.
        """
        kozak = "GCCRCCATGG"
        if sequence.upper().startswith(kozak):
            return 1.0
        return 0.0

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def encode(  # noqa: C901
        self, payload: DnaChiselEncodeRequest
    ) -> DnaChiselEncodeResponse:
        results = []
        for item in payload.items:
            # Standardize sequence to uppercase case
            sequence = item.sequence.upper()
            include = payload.params.include
            species = payload.params.species
            # Treat None and [] identically: both disable restriction site checking
            restriction_enzymes = payload.params.restriction_enzymes or []

            out = DnaChiselEncodeResponseResult()

            if DnaChiselFeatureOptions.GC_CONTENT in include:
                out.gc_content = self.compute_gc_content(sequence)

            if DnaChiselFeatureOptions.CAI in include:
                out.cai = self.compute_cai(sequence, species)

            if DnaChiselFeatureOptions.HAIRPIN_SCORE in include:
                out.hairpin_score = self.compute_hairpin_score(sequence)

            if DnaChiselFeatureOptions.MELTING_TEMPERATURE in include:
                out.melting_temperature = self.compute_melting_temperature(sequence)

            if DnaChiselFeatureOptions.RESTRICTION_SITE_COUNT in include:
                out.restriction_site_count = self.compute_restriction_site_count(
                    sequence, restriction_enzymes
                )

            if DnaChiselFeatureOptions.CODON_USAGE_ENTROPY in include:
                out.codon_usage_entropy = self.compute_codon_usage_entropy(sequence)

            if DnaChiselFeatureOptions.RARE_CODON_FREQUENCY in include:
                out.rare_codon_frequency = self.compute_rare_codon_frequency(
                    sequence, species
                )

            if DnaChiselFeatureOptions.HOMOPOLYMER_RUN_LENGTH in include:
                out.homopolymer_run_length = self.compute_homopolymer_run_length(
                    sequence
                )

            if DnaChiselFeatureOptions.DINUCLEOTIDE_FREQUENCIES in include:
                out.dinucleotide_frequencies = self.compute_dinucleotide_frequencies(
                    sequence
                )

            if DnaChiselFeatureOptions.SEQUENCE_LENGTH in include:
                out.sequence_length = self.compute_sequence_length(sequence)

            if DnaChiselFeatureOptions.TATA_BOX_COUNT in include:
                out.tata_box_count = self.compute_tata_box_count(sequence)

            if DnaChiselFeatureOptions.NON_UNIQUE_6MER_COUNT in include:
                out.non_unique_6mer_count = self.compute_non_unique_6mer_count(sequence)

            if DnaChiselFeatureOptions.IN_FRAME_STOP_CODON_COUNT in include:
                out.in_frame_stop_codon_count = self.compute_in_frame_stop_codon_count(
                    sequence
                )

            if DnaChiselFeatureOptions.METHIONINE_FREQUENCY in include:
                out.methionine_frequency = self.compute_methionine_frequency(sequence)

            if DnaChiselFeatureOptions.AT_SKEW in include:
                out.at_skew = self.compute_at_skew(sequence)

            if DnaChiselFeatureOptions.GC_SKEW in include:
                out.gc_skew = self.compute_gc_skew(sequence)

            if DnaChiselFeatureOptions.NUCLEOTIDE_ENTROPY in include:
                out.nucleotide_entropy = self.compute_nucleotide_entropy(sequence)

            if DnaChiselFeatureOptions.TANDEM_REPEAT_COUNT in include:
                out.tandem_repeat_count = self.compute_tandem_repeat_count(sequence)

            if DnaChiselFeatureOptions.GC_CONTENT_STD_DEV in include:
                out.gc_content_std_dev = self.compute_gc_content_std_dev(sequence)

            if DnaChiselFeatureOptions.KOZAK_SEQUENCE_STRENGTH in include:
                out.kozak_sequence_strength = self.compute_kozak_sequence_strength(
                    sequence
                )

            results.append(out)

        return DnaChiselEncodeResponse(results=results)


if __name__ == "__main__":
    """
    Usage:
        python models/dna_chisel/app.py

        # Force deploy:
        python models/dna_chisel/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        DnaChiselModel,
        description=f"Run and optionally deploy the {DnaChiselParams.display_name} app.",
    )
