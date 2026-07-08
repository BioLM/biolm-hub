from pathlib import Path

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
# task notes).
#
# Golden self-containment (MED-12): this used to be fetched fresh from RCSB
# inside generate(). RCSB is unpinned (no content hash / commit guarantee), so
# a byte-for-byte identical copy of the CIF fetched for the existing goldens
# is committed locally at test_data/1UBQ.cif. generate() now reads that file
# instead of hitting the network at all, so fixture generation is fully
# reproducible offline. (Verified byte-identical against a fresh RCSB fetch
# at commit time -- see MED-12 fix notes.)
_PDB_ID = "1UBQ"
_LOCAL_CIF_PATH = Path(__file__).parent / "test_data" / "1UBQ.cif"

# Sequence corresponds 1:1 to 1UBQ chain A (verified against the CIF's observed
# CA residues -- no gaps, no non-standard residues).
_SAMPLE_SEQUENCE = (
    "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG"
)


def _load_cif(pdb_id: str) -> str:
    """Load the committed local CIF structure for ``pdb_id``.

    No network access: the CIF is committed at ``test_data/<pdb_id>.cif`` so
    that both importing this module and running ``generate()`` are fully
    offline and reproducible.
    """
    if pdb_id != _PDB_ID:
        raise ValueError(f"No local CIF committed for {pdb_id!r}; expected {_PDB_ID!r}")
    return _LOCAL_CIF_PATH.read_text(encoding="utf-8")


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
    logger.info("Loading committed CIF structure from test_data/...")
    ubq_cif = _load_cif(_PDB_ID)
    logger.info("CIF structure loaded successfully")

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
