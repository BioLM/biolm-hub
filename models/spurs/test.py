from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.spurs.config import MODEL_FAMILY
from models.spurs.fixture import (
    PREDICT_MATRIX_INPUT,
    PREDICT_MATRIX_OUTPUT,
    PREDICT_MULTI_INPUT,
    PREDICT_MULTI_OUTPUT,
    PREDICT_SINGLE_INPUT,
    PREDICT_SINGLE_OUTPUT,
    PREDICT_VARIANT_INPUT,
    PREDICT_VARIANT_OUTPUT,
)

# Spurs test suite - single action (predict), multiple scenarios
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single mapping that applies to ALL variants (only one runtime)
        VariantTestMapping(
            variant_config={},  # Empty dict means applies to ALL variants
            test_cases=[
                # Test Case 1: Single mutation prediction (single ΔΔG)
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=PREDICT_SINGLE_INPUT,
                    expected_output_fixture=PREDICT_SINGLE_OUTPUT,
                    tolerances={"rel_tol": 1e-4},  # Tight numerical tolerance for ΔΔG
                ),
                # Test Case 2: Multi-mutation prediction (joint ΔΔG + contributions)
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=PREDICT_MULTI_INPUT,
                    expected_output_fixture=PREDICT_MULTI_OUTPUT,
                    tolerances={
                        "rel_tol": 1e-4
                    },  # Multi-mutation check shares tolerance
                ),
                # Test Case 3: Full matrix prediction (no mutations provided)
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=PREDICT_MATRIX_INPUT,
                    expected_output_fixture=PREDICT_MATRIX_OUTPUT,
                    tolerances={"rel_tol": 1e-4},
                ),
                # Test Case 4: variant_sequence auto-calculation
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=PREDICT_VARIANT_INPUT,
                    expected_output_fixture=PREDICT_VARIANT_OUTPUT,
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
#   pytest models/spurs/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/spurs/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/spurs/test.py -n auto --no-cov -v -s                 # both
