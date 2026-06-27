from models.clean.config import MODEL_FAMILY
from models.clean.fixture import (
    BATCH_PREDICT_INPUT,
    BATCH_PREDICT_OUTPUT,
    SINGLE_ENCODE_INPUT,
    SINGLE_ENCODE_OUTPUT,
    SINGLE_PREDICT_INPUT,
    SINGLE_PREDICT_OUTPUT,
)
from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite

# CLEAN test suite - single variant model with predict and encode actions
# Tolerances:
# - predict: 5% relative tolerance for confidence/distance values
# - encode: 0.02 cosine distance threshold for embedding similarity
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={},  # Single variant model
            test_cases=[
                # Predict tests - single sequence
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=SINGLE_PREDICT_INPUT,
                    expected_output_fixture=SINGLE_PREDICT_OUTPUT,
                    tolerances={"rel_tol": 0.05},
                ),
                # Predict tests - batch sequences
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=BATCH_PREDICT_INPUT,
                    expected_output_fixture=BATCH_PREDICT_OUTPUT,
                    tolerances={"rel_tol": 0.05},
                ),
                # Encode tests - single sequence
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=SINGLE_ENCODE_INPUT,
                    expected_output_fixture=SINGLE_ENCODE_OUTPUT,
                    tolerances={"cosine_distance_threshold": 0.02},
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
#   pytest models/clean/test.py -m integration -n auto --no-cov -v -s  # integration
#   pytest models/clean/test.py -m deployment -n auto --no-cov -v -s   # deployment
#   pytest models/clean/test.py -n auto --no-cov -v -s                 # both
