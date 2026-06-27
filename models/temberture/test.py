from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.temberture.config import MODEL_FAMILY
from models.temberture.fixture import (
    ENCODE_INPUT,
    ENCODE_OUTPUT_TPL,
    PREDICT_INPUT,
    PREDICT_OUTPUT_TPL,
)

# TemBERTure test suite - two actions (encode, predict), two model types
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Classifier model variant
        VariantTestMapping(
            variant_config={"MODEL_TYPE": "classifier"},
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=ENCODE_INPUT,
                    expected_output_fixture=ENCODE_OUTPUT_TPL,
                    tolerances={"rel_tol": 1e-4, "cosine_distance_threshold": 0.02},
                ),
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=PREDICT_INPUT,
                    expected_output_fixture=PREDICT_OUTPUT_TPL,
                    tolerances={"rel_tol": 1e-4},  # Temperature prediction tolerance
                ),
            ],
        ),
        # Regression model variant
        VariantTestMapping(
            variant_config={"MODEL_TYPE": "regression"},
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=ENCODE_INPUT,
                    expected_output_fixture=ENCODE_OUTPUT_TPL,
                    tolerances={"rel_tol": 1e-4, "cosine_distance_threshold": 0.02},
                ),
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=PREDICT_INPUT,
                    expected_output_fixture=PREDICT_OUTPUT_TPL,
                    tolerances={"rel_tol": 1e-4},  # Temperature prediction tolerance
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
#   pytest models/temberture/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/temberture/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/temberture/test.py -n auto --no-cov -v -s                 # both
