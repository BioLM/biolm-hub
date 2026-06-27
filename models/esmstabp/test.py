from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.esmstabp.config import MODEL_FAMILY
from models.esmstabp.fixture import (
    PREDICT_ALL_FEATURES_INPUT,
    PREDICT_ALL_FEATURES_OUTPUT,
    PREDICT_INPUT,
    PREDICT_OUTPUT,
    PREDICT_WITH_CONDITION_INPUT,
    PREDICT_WITH_CONDITION_OUTPUT,
    PREDICT_WITH_GROWTH_TEMP_INPUT,
    PREDICT_WITH_GROWTH_TEMP_OUTPUT,
)

# Temperature prediction tolerances:
# - rel_tol=0.02 (2%): At 50C = 1C variance, at 80C = 1.6C variance
TEMP_TOLERANCES = {"rel_tol": 0.02}

# ESMStabP test suite - single variant, 4 test cases (one per RF model)
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single variant mapping (empty config = applies to all)
        VariantTestMapping(
            variant_config={},
            test_cases=[
                # Test Case 1: Model 1 - embedding only
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=PREDICT_INPUT,
                    expected_output_fixture=PREDICT_OUTPUT,
                    tolerances=TEMP_TOLERANCES,
                ),
                # Test Case 2: Model 2 - with growth_temp
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=PREDICT_WITH_GROWTH_TEMP_INPUT,
                    expected_output_fixture=PREDICT_WITH_GROWTH_TEMP_OUTPUT,
                    tolerances=TEMP_TOLERANCES,
                ),
                # Test Case 3: Model 3 - with experimental_condition
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=PREDICT_WITH_CONDITION_INPUT,
                    expected_output_fixture=PREDICT_WITH_CONDITION_OUTPUT,
                    tolerances=TEMP_TOLERANCES,
                ),
                # Test Case 4: Model 4 - all features
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=PREDICT_ALL_FEATURES_INPUT,
                    expected_output_fixture=PREDICT_ALL_FEATURES_OUTPUT,
                    tolerances=TEMP_TOLERANCES,
                ),
            ],
        ),
    ],
)

# Generate integration tests (marked with @pytest.mark.integration)
generate_tests_from_suite(test_suite, test_type="integration")

# Generate deployment tests (marked with @pytest.mark.deployment)
generate_tests_from_suite(test_suite, test_type="deployment")

# Usage:
#   pytest models/esmstabp/test.py -m integration -n auto --no-cov -v -s
#   pytest models/esmstabp/test.py -m deployment -n auto --no-cov -v -s
#   pytest models/esmstabp/test.py -n auto --no-cov -v -s  # both
