from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.omni_dna.config import MODEL_FAMILY
from models.omni_dna.fixture import (
    ENCODE_INPUT,
    ENCODE_OUTPUT_TPL,
    LOGPROB_INPUT,
    LOGPROB_OUTPUT_TPL,
)

# Omni-DNA test suite - ONLY 1b variant has test files
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Only test the 1b variant
        VariantTestMapping(
            variant_config={"MODEL_SIZE": "1b"},  # Only test 1b variant
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=ENCODE_INPUT,
                    # Template: will be formatted with variant.name (e.g., "1b_encode_expected_output.json")
                    expected_output_fixture=ENCODE_OUTPUT_TPL,
                    tolerances={"rel_tol": 1e-4},
                ),
                ActionTestCase(
                    action_name=ModelActions.LOG_PROB,
                    input_fixture=LOGPROB_INPUT,
                    # Template: will be formatted with variant.name (e.g., "1b_logprob_expected_output.json")
                    expected_output_fixture=LOGPROB_OUTPUT_TPL,
                    tolerances={"rel_tol": 1e-4},
                ),
            ],
        )
    ],
)

# Generate integration tests (marked with @pytest.mark.integration)
test_omni_dna_integration = generate_tests_from_suite(
    test_suite, test_type="integration"
)

# Generate deployment tests (marked with @pytest.mark.deployment)
test_omni_dna_deployment = generate_tests_from_suite(test_suite, test_type="deployment")

# Usage:
#   pytest models/omni_dna/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/omni_dna/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/omni_dna/test.py -n auto --no-cov -v -s                 # both
