from typing import cast
from urllib.error import URLError
from urllib.request import urlopen

from models.commons.core.logging import get_logger
from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.prody.config import MODEL_FAMILY
from models.prody.schema import (
    AlignmentMethod,
    HydrogenMethod,
    ProDyEncodeRequest,
    ProDyEncodeRequestItem,
    ProDyEncodeRequestParams,
    ProDyPredictRequest,
    ProDyPredictRequestItem,
    ProDyPredictRequestParams,
)

logger = get_logger(__name__)

# Fixture filename constants
ENCODE_INPUT = "encode_input.json"
ENCODE_OUTPUT = "encode_expected_output.json"
PREDICT_INPUT = "predict_input.json"
PREDICT_OUTPUT = "predict_expected_output.json"


# Download CIF files from RCSB inline
def _download_cif(pdb_id: str) -> str:
    """Download CIF file from RCSB and return as string."""
    url = f"https://files.rcsb.org/download/{pdb_id}.cif"
    try:
        with urlopen(url, timeout=10) as response:
            return cast(str, response.read().decode("utf-8"))
    except URLError as e:
        raise ValueError(f"Failed to download CIF for {pdb_id}: {e}") from e


# TestSuite skeleton — test cases are built lazily inside generate() to avoid
# module-scope network calls (RCSB CIF downloads) that would break --collect-only.
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={},
            test_cases=[],  # populated by generate()
        )
    ],
)


def generate() -> None:
    """Configures and runs the fixture generator for prody model"""
    # Download test structures lazily (inside generate, not at module scope)
    # 3IY3: Multi-chain complex with A and B protein chains (good for multi-chain tests)
    # 1UBQ: Ubiquitin - single chain, small protein (~76 residues)
    # 1CRN: Crambin - single chain, small protein (~46 residues, different length from 1UBQ)
    logger.info("Downloading CIF files from RCSB...")
    cif_3iy3 = _download_cif("3IY3")
    cif_1ubq = _download_cif("1UBQ")
    cif_1crn = _download_cif("1CRN")
    logger.info("CIF files downloaded successfully")

    # Rebuild test cases with the freshly downloaded CIFs
    fixture_generation_suite.variant_test_mappings[0].test_cases = [
        # Test Case 1: Encode (InSty) - Single chain (1UBQ)
        ActionTestCase(
            action_name=ModelActions.ENCODE,
            input_fixture=ProDyEncodeRequest(
                params=ProDyEncodeRequestParams(
                    add_hydrogens=True,
                    hydrogen_method=HydrogenMethod.OPENBABEL,
                ),
                items=[
                    ProDyEncodeRequestItem(
                        cif=cif_1ubq,
                        chain_ids=["A"],
                    )
                ],
            ),
            input_filename_template="encode_single_chain_input_v2.json",
            expected_output_fixture="encode_single_chain_expected_output_v2.json",
            tolerances={"rel_tol": 1e-2},
        ),
        # Test Case 2: Encode (InSty) - Multi-chain (3IY3)
        ActionTestCase(
            action_name=ModelActions.ENCODE,
            input_fixture=ProDyEncodeRequest(
                params=ProDyEncodeRequestParams(
                    add_hydrogens=True,
                    hydrogen_method=HydrogenMethod.OPENBABEL,
                ),
                items=[
                    ProDyEncodeRequestItem(
                        cif=cif_3iy3,
                        chain_ids=["A", "B"],
                        chain_pairs=[("A", "B")],
                    )
                ],
            ),
            input_filename_template="encode_multi_chain_input_v2.json",
            expected_output_fixture="encode_multi_chain_expected_output_v2.json",
            tolerances={"rel_tol": 1e-2},
        ),
        # Test Case 3: Predict (RMSD) - Single chain, same structure (should be ~0 RMSD)
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=ProDyPredictRequest(
                params=ProDyPredictRequestParams(
                    alignment_method=AlignmentMethod.STRUCTURAL,
                ),
                items=[
                    ProDyPredictRequestItem(
                        cif_a=cif_1ubq,
                        chain_a="A",
                        cif_b=cif_1ubq,
                        chain_b="A",
                    )
                ],
            ),
            input_filename_template="predict_single_chain_same_input.json",
            expected_output_fixture="predict_single_chain_same_expected_output.json",
            tolerances={"rel_tol": 1e-2},
        ),
        # Test Case 4: Predict (RMSD) - Multi-chain, same chains
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=ProDyPredictRequest(
                params=ProDyPredictRequestParams(
                    alignment_method=AlignmentMethod.STRUCTURAL,
                ),
                items=[
                    ProDyPredictRequestItem(
                        cif_a=cif_3iy3,
                        chain_a="A",
                        cif_b=cif_3iy3,
                        chain_b="A",
                    )
                ],
            ),
            input_filename_template="predict_multi_chain_same_input.json",
            expected_output_fixture="predict_multi_chain_same_expected_output.json",
            tolerances={"rel_tol": 1e-2},
        ),
        # Test Case 5: Predict (RMSD) - Different chain lengths (1UBQ vs 1CRN)
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=ProDyPredictRequest(
                params=ProDyPredictRequestParams(
                    alignment_method=AlignmentMethod.SEQUENCE,
                ),
                items=[
                    ProDyPredictRequestItem(
                        cif_a=cif_1ubq,
                        chain_a="A",
                        cif_b=cif_1crn,
                        chain_b="A",
                    )
                ],
            ),
            input_filename_template="predict_different_lengths_input.json",
            expected_output_fixture="predict_different_lengths_expected_output.json",
            tolerances={"rel_tol": 1e-2},
        ),
    ]

    generator = FixtureGenerator(fixture_generation_suite)
    generator.generate()


if __name__ == "__main__":
    generate()

# Run with: python models/prody/fixture.py
