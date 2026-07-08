from typing import Any, Optional

from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.mpnn.config import MODEL_FAMILY
from models.mpnn.fixture import INPUT1
from models.mpnn.schema import MPNNModelTypes


def _validate_mpnn_generate(
    actual_output: dict[str, Any], _expected_output: Optional[dict[str, Any]] = None
) -> None:
    """Structural validation for MPNN generate output."""
    assert "results" in actual_output, "Response missing 'results' key"
    results = actual_output["results"]
    assert len(results) > 0, "Results list is empty"
    for idx, result in enumerate(results):
        assert "sequence" in result, f"Result {idx} missing 'sequence' field"
        assert (
            isinstance(result["sequence"], str) and len(result["sequence"]) > 0
        ), f"Result {idx} 'sequence' is empty or not a string"
        assert "pdb" in result, f"Result {idx} missing 'pdb' field"
        assert (
            isinstance(result["pdb"], str) and len(result["pdb"]) > 0
        ), f"Result {idx} 'pdb' is empty or not a string"
        for conf_field in ("overall_confidence", "ligand_confidence"):
            assert conf_field in result, f"Result {idx} missing '{conf_field}' field"
            val = float(result[conf_field])
            assert (
                0.0 <= val <= 1.0
            ), f"Result {idx} '{conf_field}' value {val} is outside [0, 1]"


# MPNN test suite — test all 6 deployable variants (protein, ligand, soluble,
# global_label_membrane, per_residue_label_membrane, hyper) with 1 input each.
# The full 6-variant x 4-input matrix (24 tests) exceeds CI timeout, so each
# variant runs the single canonical INPUT1 backbone. The two membrane variants
# are included to catch regressions in the membrane-aware code paths.
#
# Structural validator (not a numeric golden comparison) is deliberate: ProteinMPNN
# GENERATES sequences by temperature-sampling the per-residue distribution, so the
# designed sequence — and the packed side-chain PDB / confidence scores derived from
# it — vary run to run. There is no fixed "golden" to compare numerically; the
# validator asserts the output is well-formed (non-empty sequence + PDB, confidences
# in [0, 1]) instead.
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={"MODEL_TYPE": MPNNModelTypes.PROTEIN},
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=INPUT1,
                    validator=_validate_mpnn_generate,
                ),
            ],
        ),
        VariantTestMapping(
            variant_config={"MODEL_TYPE": MPNNModelTypes.LIGAND},
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=INPUT1,
                    validator=_validate_mpnn_generate,
                ),
            ],
        ),
        VariantTestMapping(
            variant_config={"MODEL_TYPE": MPNNModelTypes.SOLUBLE},
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=INPUT1,
                    validator=_validate_mpnn_generate,
                ),
            ],
        ),
        VariantTestMapping(
            variant_config={"MODEL_TYPE": MPNNModelTypes.GLOBAL_LABEL_MEMBRANE},
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=INPUT1,
                    validator=_validate_mpnn_generate,
                ),
            ],
        ),
        VariantTestMapping(
            variant_config={"MODEL_TYPE": MPNNModelTypes.PER_RESIDUE_LABEL_MEMBRANE},
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=INPUT1,
                    validator=_validate_mpnn_generate,
                ),
            ],
        ),
        VariantTestMapping(
            variant_config={"MODEL_TYPE": MPNNModelTypes.HYPER},
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=INPUT1,
                    validator=_validate_mpnn_generate,
                ),
            ],
        ),
    ],
)


# Generate integration tests (marked with @pytest.mark.integration)
test_mpnn_integration = generate_tests_from_suite(test_suite, test_type="integration")

# Generate deployment tests (marked with @pytest.mark.deployment)
test_mpnn_deployment = generate_tests_from_suite(test_suite, test_type="deployment")

# Usage:
#   pytest models/mpnn/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/mpnn/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/mpnn/test.py -n auto --no-cov -v -s                 # both
