"""ImmuneFold golden-fixture generation.

Inputs are self-contained: the paired-antibody, nanobody, and TCR cases use
inline canonical sequences, and the antibody-antigen complex case reads a
small antigen structure committed locally under `test_data/` (byte-identical
to the RCSB source it was fetched from). No pre-existing R2 input is
required — the generator writes each input to R2 alongside the generated
expected output.
"""

from pathlib import Path

from models.commons.core.logging import get_logger
from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.immunefold.config import MODEL_FAMILY
from models.immunefold.schema import (
    ImmuneFoldPredictRequest,
    ImmuneFoldPredictRequestItem,
)

logger = get_logger(__name__)

# Test input/output filenames. Inputs are self-contained (inlined sequences
# / a local fixture file below), so generation needs no pre-existing R2
# assets — the generator writes these inputs to R2 alongside the generated
# outputs.
# ImmuNeFold has multiple input files per variant type
ANTIGEN_PREDICT_INPUT = "antigen_predict_input.json"
ANTIBODY_PREDICT_INPUT = "antibody_predict_input.json"
NANOBODY_PREDICT_INPUT = "nanobody_predict_input.json"
TCR_PREDICT_INPUT = "tcr_predict_input.json"

ANTIGEN_PREDICT_OUTPUT = "antigen_predict_expected_output.json"
ANTIBODY_PREDICT_OUTPUT = "antibody_predict_expected_output.json"
NANOBODY_PREDICT_OUTPUT = "nanobody_predict_expected_output.json"
TCR_PREDICT_OUTPUT = "tcr_predict_expected_output.json"

# Canonical paired-antibody heavy/light chains (from README.md's "Paired
# antibody" example) — well above the IMGT minimums (VH >= 90, VL >= 85 AA).
HEAVY_CHAIN = (
    "EVQLVESGGGLVQPGGSLRLSCAASGFTFSDYAMSWVRQAPGKGLEWVSGISGSGGSTYYADSVKGRFTIS"
    "RDNSKNTLYLQMNSLRAEDTAVYYCAKDRLSITIRPRYYGLDVWGQGTTVTVSS"
)
LIGHT_CHAIN = (
    "DIQMTQSPSSLSASVGDRVTITCRASQSISSYLNWYQQKPGKAPKLLIYAASSLQSGVPSRFSGSGSGTDF"
    "TLTISSLQPEDFATYYCQQSYSTPLTFGGGTKVEIK"
)

# Canonical nanobody (VHH, heavy-chain-only) sequence, from README.md.
NANOBODY_HEAVY_CHAIN = (
    "QVQLQESGGGLVQPGGSLRLSCAASGRTFSSYAMGWFRQAPGKEREFVAAISWSGGSTYYADSVKGRFTIS"
    "RDNAKNTVYLQMNSLKPEDTAVYYCAADSTIYASYYECGHGLSTGGYGYDSWGQGTQVTVSS"
)

# Canonical alpha/beta TCR with peptide-MHC context (influenza M1 peptide
# GILGFVFTL presented on an HLA class I heavy chain), from README.md.
TCR_BETA = (
    "DAGVTQTPRNHVTISEGDKITVRCEKSTVSNFLYELFWYRQDPGLGLRLIYFSYDVKMKEKGDIPDGYSVS"
    "RNKKPNFYEALISKLNVSDSALYFCASSQETQYFGPGTRLTVL"
)
TCR_ALPHA = (
    "AQEVTQIPAALSVPEGENLVLNCSFTDSAIYNLQWFRQDPGKGLTSLLLIQSSQREQTSGRLNASLDKSSG"
    "RSTLYIAASQPGDSATYLCAVRPTSGGSYIPTFGRGTSLIVHPY"
)
TCR_PEPTIDE = "GILGFVFTL"
TCR_MHC = (
    "GSHSMRYFFTSVSRPGRGEPRFIAVGYVDDTQFVRFDSDAASQRMEPRAPWIEQEGPEYWDGETRKVKAHS"
    "QTHRVDLGTLRGYYNQSEAGSHTVQRMYGCDVGSDWRFLRGYHQYAYDGKDY"
)

# Small antigen structure for the antibody-antigen complex test case,
# committed locally (legacy PDB format, required by the `pdb` field) as
# byte-identical to `https://files.rcsb.org/download/1LYZ.pdb` so golden
# generation is self-contained and doesn't depend on RCSB being reachable.
_ANTIGEN_PDB_ID = "1LYZ"  # Hen egg-white lysozyme; small (~129 aa) single-chain antigen
_TEST_DATA_DIR = Path(__file__).parent / "test_data"
_ANTIGEN_PDB_PATH = _TEST_DATA_DIR / f"{_ANTIGEN_PDB_ID}.pdb"


def _load_pdb(path: Path) -> str:
    """Read a local legacy PDB-format structure file and return it as text."""
    return path.read_text(encoding="utf-8")


def _build_fixture_generation_suite() -> TestSuite:
    """Build the fixture-generation suite skeleton (antibody + tcr variants).

    The antibody-antigen complex test case is appended in generate() once the
    antigen PDB has been loaded from the local `test_data/` fixture.
    """
    antibody_request = ImmuneFoldPredictRequest(
        items=[
            ImmuneFoldPredictRequestItem(
                heavy_chain=HEAVY_CHAIN,
                light_chain=LIGHT_CHAIN,
            )
        ],
    )
    nanobody_request = ImmuneFoldPredictRequest(
        items=[ImmuneFoldPredictRequestItem(heavy_chain=NANOBODY_HEAVY_CHAIN)],
    )
    tcr_request = ImmuneFoldPredictRequest(
        items=[
            ImmuneFoldPredictRequestItem(
                tcr_beta=TCR_BETA,
                tcr_alpha=TCR_ALPHA,
                peptide=TCR_PEPTIDE,
                mhc=TCR_MHC,
            )
        ],
    )

    return TestSuite(
        model_family=MODEL_FAMILY,
        r2_fixture_subdir="models",
        variant_test_mappings=[
            # Antibody variant - has 3 input types (antigen case added in generate())
            VariantTestMapping(
                variant_config={"MODEL_TYPE": "antibody"},
                test_cases=[
                    ActionTestCase(
                        action_name=ModelActions.FOLD,
                        input_fixture=antibody_request,
                        input_filename_template=ANTIBODY_PREDICT_INPUT,
                        expected_output_fixture=ANTIBODY_PREDICT_OUTPUT,
                        tolerances={"rel_tol": 1e-4, "pdb_rmsd_threshold": 1e-4},
                    ),
                    ActionTestCase(
                        action_name=ModelActions.FOLD,
                        input_fixture=nanobody_request,
                        input_filename_template=NANOBODY_PREDICT_INPUT,
                        expected_output_fixture=NANOBODY_PREDICT_OUTPUT,
                        tolerances={"rel_tol": 1e-4, "pdb_rmsd_threshold": 1e-4},
                    ),
                ],
            ),
            # TCR variant - has 1 input type
            VariantTestMapping(
                variant_config={"MODEL_TYPE": "tcr"},
                test_cases=[
                    ActionTestCase(
                        action_name=ModelActions.FOLD,
                        input_fixture=tcr_request,
                        input_filename_template=TCR_PREDICT_INPUT,
                        expected_output_fixture=TCR_PREDICT_OUTPUT,
                        tolerances={"rel_tol": 1e-4, "pdb_rmsd_threshold": 1e-4},
                    ),
                ],
            ),
        ],
    )


def generate() -> None:
    """Configures and runs the fixture generator for both ImmuneFold variants."""
    suite = _build_fixture_generation_suite()

    logger.info(f"Loading local antigen PDB {_ANTIGEN_PDB_ID}...")
    antigen_pdb = _load_pdb(_ANTIGEN_PDB_PATH)
    logger.info("Antigen PDB loaded successfully")

    antigen_request = ImmuneFoldPredictRequest(
        items=[
            ImmuneFoldPredictRequestItem(
                heavy_chain=HEAVY_CHAIN,
                light_chain=LIGHT_CHAIN,
                pdb=antigen_pdb,
            )
        ],
    )
    # Prepend so the antigen case generates alongside the other antibody cases.
    suite.variant_test_mappings[0].test_cases.insert(
        0,
        ActionTestCase(
            action_name=ModelActions.FOLD,
            input_fixture=antigen_request,
            input_filename_template=ANTIGEN_PREDICT_INPUT,
            expected_output_fixture=ANTIGEN_PREDICT_OUTPUT,
            tolerances={"rel_tol": 1e-4, "pdb_rmsd_threshold": 1e-4},
        ),
    )

    generator = FixtureGenerator(suite)
    generator.generate()


if __name__ == "__main__":
    generate()

# Run with: python models/immunefold/fixture.py
