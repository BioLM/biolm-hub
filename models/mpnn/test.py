from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.mpnn.config import MODEL_FAMILY
from models.mpnn.fixture import INPUT1
from models.mpnn.schema import MPNNModelTypes


def _validate_mpnn_generate(actual_output: dict, _expected_output: dict = None):
    """Basic validation for MPNN generate output - just check structure."""
    assert "results" in actual_output, "Response missing 'results' key"
    assert len(actual_output["results"]) > 0, "Results list is empty"


# MPNN test suite — test 2 representative variants (protein + ligand) with 1 input each.
# Full 6-variant x 4-input matrix (24 tests) exceeds CI timeout. This gives coverage
# of both base MPNN and LigandMPNN with minimal runtime.
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
