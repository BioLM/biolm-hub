from models.chemberta.config import MODEL_FAMILY
from models.chemberta.fixture import (
    ENCODE_INPUT,
    ENCODE_OUTPUT,
    LOGPROB_INPUT,
    LOGPROB_OUTPUT,
)
from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite

# ChemBERTa test suite - single variant model with two actions (encode, log_prob).
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single mapping that applies to the single variant
        VariantTestMapping(
            variant_config={},  # Empty dict means applies to ALL variants (only one here)
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=ENCODE_INPUT,
                    expected_output_fixture=ENCODE_OUTPUT,
                    tolerances={"rel_tol": 1e-4},
                ),
                ActionTestCase(
                    action_name=ModelActions.LOG_PROB,
                    input_fixture=LOGPROB_INPUT,
                    expected_output_fixture=LOGPROB_OUTPUT,
                    tolerances={"rel_tol": 1e-4},
                ),
            ],
        )
    ],
)

# Generate integration tests (marked with @pytest.mark.integration)
test_chemberta_integration = generate_tests_from_suite(
    test_suite, test_type="integration"
)

# Generate deployment tests (marked with @pytest.mark.deployment)
test_chemberta_deployment = generate_tests_from_suite(
    test_suite, test_type="deployment"
)

# Usage:
#   pytest models/chemberta/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/chemberta/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/chemberta/test.py -n auto --no-cov -v -s                 # both
