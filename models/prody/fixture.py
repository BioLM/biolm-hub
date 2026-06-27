from urllib.error import URLError
from urllib.request import urlopen

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
            return response.read().decode("utf-8")
    except URLError as e:
        raise ValueError(f"Failed to download CIF for {pdb_id}: {e}") from e


# Download test structures
# 3IY3: Multi-chain complex with A and B protein chains (good for multi-chain tests)
# 1UBQ: Ubiquitin - single chain, small protein (~76 residues, good for single chain tests)
# 1CRN: Crambin - single chain, small protein (~46 residues, different length from 1UBQ)
print("Downloading CIF files from RCSB...")
_CIF_3IY3 = _download_cif("3IY3")  # Multi-chain complex with A and B protein chains
_CIF_1UBQ = _download_cif("1UBQ")  # Single chain protein (~76 residues)
_CIF_1CRN = _download_cif(
    "1CRN"
)  # Single chain protein (~46 residues, different length)
print("CIF files downloaded successfully")

# TestSuite for fixture generation
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={},
            test_cases=[
                # Encode (InSty) Tests
                # Test Case 1: Encode (InSty) - Single chain (1UBQ)
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=ProDyEncodeRequest(
                        params=ProDyEncodeRequestParams(
                            add_hydrogens=True,
                            hydrogen_method=HydrogenMethod.OPENBABEL,
                            compute_all_interactions=True,
                        ),
                        items=[
                            ProDyEncodeRequestItem(
                                cif=_CIF_1UBQ,
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
                            compute_all_interactions=True,
                        ),
                        items=[
                            ProDyEncodeRequestItem(
                                cif=_CIF_3IY3,
                                chain_ids=["A", "B"],
                                chain_pairs=[("A", "B")],
                            )
                        ],
                    ),
                    input_filename_template="encode_multi_chain_input_v2.json",
                    expected_output_fixture="encode_multi_chain_expected_output_v2.json",
                    tolerances={"rel_tol": 1e-2},
                ),
                # Predict (RMSD) Tests
                # Test Case 3: Predict (RMSD) - Single chain, same structure (should be ~0 RMSD)
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=ProDyPredictRequest(
                        params=ProDyPredictRequestParams(
                            alignment_method=AlignmentMethod.STRUCTURAL,
                        ),
                        items=[
                            ProDyPredictRequestItem(
                                cif_a=_CIF_1UBQ,
                                chain_a="A",
                                cif_b=_CIF_1UBQ,
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
                                cif_a=_CIF_3IY3,
                                chain_a="A",
                                cif_b=_CIF_3IY3,
                                chain_b="A",
                            )
                        ],
                    ),
                    input_filename_template="predict_multi_chain_same_input.json",
                    expected_output_fixture="predict_multi_chain_same_expected_output.json",
                    tolerances={"rel_tol": 1e-2},
                ),
                # Test Case 5: Predict (RMSD) - Different chain lengths (1UBQ vs 1CRN)
                # 1UBQ has ~76 residues, 1CRN has ~46 residues - different lengths
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=ProDyPredictRequest(
                        params=ProDyPredictRequestParams(
                            alignment_method=AlignmentMethod.SEQUENCE,  # Use sequence alignment for different lengths
                        ),
                        items=[
                            ProDyPredictRequestItem(
                                cif_a=_CIF_1UBQ,
                                chain_a="A",
                                cif_b=_CIF_1CRN,
                                chain_b="A",  # Different structures with different chain lengths
                            )
                        ],
                    ),
                    input_filename_template="predict_different_lengths_input.json",
                    expected_output_fixture="predict_different_lengths_expected_output.json",
                    tolerances={"rel_tol": 1e-2},
                ),
            ],
        )
    ],
)


def generate():
    """Configures and runs the fixture generator for prody model"""
    generator = FixtureGenerator(fixture_generation_suite)
    generator.generate()


if __name__ == "__main__":
    generate()

# Run with: python models/prody/fixture.py
