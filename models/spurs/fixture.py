from urllib.error import URLError
from urllib.request import urlopen

from models.commons.core.logging import get_logger
from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.spurs.config import MODEL_FAMILY
from models.spurs.schema import (
    SpursPredictRequest,
    SpursPredictRequestItem,
)

logger = get_logger(__name__)

# Fixture filename constants
PREDICT_SINGLE_INPUT = "predict_single_input.json"
PREDICT_MULTI_INPUT = "predict_multi_input.json"
PREDICT_SINGLE_OUTPUT = "predict_single_expected_output.json"
PREDICT_MULTI_OUTPUT = "predict_multi_expected_output.json"
PREDICT_MATRIX_INPUT = "predict_matrix_input.json"
PREDICT_MATRIX_OUTPUT = "predict_matrix_expected_output.json"
PREDICT_VARIANT_INPUT = "predict_variant_input.json"
PREDICT_VARIANT_OUTPUT = "predict_variant_expected_output.json"

# 1UBQ: human ubiquitin, single chain (A), 76 residues -- small, canonical,
# high-resolution (1.8 A) structure with no missing/disordered residues, so
# chain A's observed CA sequence is exactly the full 76-residue sequence below
# (verified independently against the fetched CIF; see fixture.py history /
# task notes). Fetched fresh from RCSB inside generate() (not at module scope)
# so importing this module never touches the network.
_PDB_ID = "1UBQ"

# Sequence corresponds 1:1 to 1UBQ chain A (verified against the CIF's observed
# CA residues -- no gaps, no non-standard residues).
_SAMPLE_SEQUENCE = (
    "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG"
)


def _download_cif(pdb_id: str) -> str:
    """Download a CIF structure from RCSB and return it as text.

    Network access lives here, NOT at module scope, so importing this module
    (e.g. for ``pytest --collect-only`` via test.py) never touches the network.
    Only ``generate()`` (run explicitly) downloads the structure.
    """
    url = f"https://files.rcsb.org/download/{pdb_id}.cif"
    try:
        with urlopen(url, timeout=10) as response:
            raw: bytes = response.read()
            return raw.decode("utf-8")
    except URLError as e:
        raise ValueError(f"Failed to download CIF for {pdb_id}: {e}") from e


# Create TestSuite for fixture generation with programmatic inputs
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={},
            test_cases=[],
        )
    ],
)


def generate() -> None:
    """Configures and runs the fixture generator"""
    logger.info("Downloading CIF structure from RCSB...")
    ubq_cif = _download_cif(_PDB_ID)
    logger.info("CIF structure downloaded successfully")

    # Variant sequence with K48R and K63R applied (0-indexed positions 47, 62),
    # for the variant_sequence auto-calculation test case (Test Case 4 below).
    variant_chars = list(_SAMPLE_SEQUENCE)
    variant_chars[47] = "R"  # K48R (0-indexed: 47)
    variant_chars[62] = "R"  # K63R (0-indexed: 62)
    variant_sequence = "".join(variant_chars)

    # Test Case 1: single mutation prediction.
    # I44A disrupts ubiquitin's classic hydrophobic patch (Leu8/Ile44/Val70),
    # the surface used by most ubiquitin-binding domains.
    fixture_generation_suite.variant_test_mappings[0].test_cases = [
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=SpursPredictRequest(
                items=[
                    SpursPredictRequestItem(
                        sequence=_SAMPLE_SEQUENCE,
                        cif=ubq_cif,
                        mutations=["I44A"],
                    )
                ]
            ),
            input_filename_template=PREDICT_SINGLE_INPUT,
            expected_output_fixture=PREDICT_SINGLE_OUTPUT,
            tolerances={"rel_tol": 1e-4},
        ),
        # Test Case 2: multi-mutation prediction.
        # K48R and K63R are ubiquitin's two canonical chain-linkage lysines
        # (K48-linked chains signal proteasomal degradation; K63-linked chains
        # signal non-degradative pathways).
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=SpursPredictRequest(
                items=[
                    SpursPredictRequestItem(
                        sequence=_SAMPLE_SEQUENCE,
                        cif=ubq_cif,
                        mutations=["K48R", "K63R"],
                    )
                ]
            ),
            input_filename_template=PREDICT_MULTI_INPUT,
            expected_output_fixture=PREDICT_MULTI_OUTPUT,
            tolerances={"rel_tol": 1e-4},
        ),
        # Test Case 3: full matrix prediction (no explicit mutations)
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=SpursPredictRequest(
                items=[
                    SpursPredictRequestItem(
                        sequence=_SAMPLE_SEQUENCE,
                        cif=ubq_cif,
                        mutations=None,
                    )
                ]
            ),
            input_filename_template=PREDICT_MATRIX_INPUT,
            expected_output_fixture=PREDICT_MATRIX_OUTPUT,
            tolerances={"rel_tol": 1e-4},
        ),
        # Test Case 4: variant_sequence auto-calculation (K48R, K63R from variant)
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=SpursPredictRequest(
                items=[
                    SpursPredictRequestItem(
                        sequence=_SAMPLE_SEQUENCE,  # Wild-type
                        variant_sequence=variant_sequence,  # K48R, K63R
                        cif=ubq_cif,
                        mutations=None,
                        return_full_dms=False,
                    )
                ]
            ),
            input_filename_template=PREDICT_VARIANT_INPUT,
            expected_output_fixture=PREDICT_VARIANT_OUTPUT,
            tolerances={"rel_tol": 1e-4},
        ),
    ]

    generator = FixtureGenerator(fixture_generation_suite)
    generator.generate()


if __name__ == "__main__":
    generate()

# Run with: python models/spurs/fixture.py
