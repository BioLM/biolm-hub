from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.tempro.config import MODEL_FAMILY
from models.tempro.fixture import (
    PREDICT_BATCH_INPUT,
    PREDICT_BATCH_OUTPUT_TPL,
    PREDICT_SINGLE_INPUT,
    PREDICT_SINGLE_OUTPUT_TPL,
    PREDICT_VALIDATION_INPUT,
    PREDICT_VALIDATION_OUTPUT_TPL,
)

# TEMPRO test suite - single action (predict), multiple test scenarios
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single mapping that applies to ALL variants (both 650m and 3b)
        VariantTestMapping(
            variant_config={},  # Empty dict means applies to ALL variants
            test_cases=[
                # Test Case 1: Single sequence prediction
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=PREDICT_SINGLE_INPUT,
                    expected_output_fixture=PREDICT_SINGLE_OUTPUT_TPL,
                ),
                # Test Case 2: Batch prediction (4 sequences)
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=PREDICT_BATCH_INPUT,
                    expected_output_fixture=PREDICT_BATCH_OUTPUT_TPL,
                ),
                # Test Case 3: Validation sequences with known Tms (all 6 sequences)
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=PREDICT_VALIDATION_INPUT,
                    expected_output_fixture=PREDICT_VALIDATION_OUTPUT_TPL,
                    tolerances={
                        "rel_tol": 0.1
                    },  # 10% relative tolerance for Tm predictions
                ),
            ],
        )
    ],
)


# Generate integration tests (marked with @pytest.mark.integration)
test_tempro_integration = generate_tests_from_suite(test_suite, test_type="integration")

# Generate deployment tests (marked with @pytest.mark.deployment)
test_tempro_deployment = generate_tests_from_suite(test_suite, test_type="deployment")

# Usage:
#   pytest models/tempro/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/tempro/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/tempro/test.py -n auto --no-cov -v -s                 # both
