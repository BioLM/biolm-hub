from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.peptides.config import MODEL_FAMILY
from models.peptides.fixture import (
    MULTIPLE_ENCODE_OUTPUT,
    MULTIPLE_SEQS_INPUT,
    SINGLE_ENCODE_OUTPUT,
    SINGLE_SEQ_INPUT,
)

# Peptides test suite - single variant, multiple test cases
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single mapping for the single variant
        VariantTestMapping(
            variant_config={},  # Empty dict for single variant
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=SINGLE_SEQ_INPUT,
                    expected_output_fixture=SINGLE_ENCODE_OUTPUT,
                    tolerances={"rel_tol": 1e-4},
                ),
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=MULTIPLE_SEQS_INPUT,
                    expected_output_fixture=MULTIPLE_ENCODE_OUTPUT,
                    tolerances={"rel_tol": 1e-4},
                ),
            ],
        )
    ],
)

# Generate integration tests (marked with @pytest.mark.integration)
generate_tests_from_suite(test_suite, test_type="integration")

# Generate deployment tests (marked with @pytest.mark.deployment)
generate_tests_from_suite(test_suite, test_type="deployment")

# Usage:
#   pytest models/peptides/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/peptides/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/peptides/test.py -n auto --no-cov -v -s                 # both
