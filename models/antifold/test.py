from models.antifold.config import MODEL_FAMILY
from models.antifold.fixture import (
    ENCODE_3HFM_INPUT,
    ENCODE_3HFM_OUTPUT,
    ENCODE_8OI2_INPUT,
    ENCODE_8OI2_OUTPUT,
    GENERATE_3HFM_INPUT,
    GENERATE_3HFM_OUTPUT,
    GENERATE_6Y1L_INPUT,
    GENERATE_6Y1L_OUTPUT,
    GENERATE_8OI2_INPUT,
    GENERATE_8OI2_OUTPUT,
    LOGPROB_3HFM_INPUT,
    LOGPROB_3HFM_OUTPUT,
    SCORE_3HFM_OUTPUT,
)
from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite


def _validate_antifold_generate(
    actual_output: dict, expected_output: dict | None = None
):
    """Custom validator for AntiFold generate method from original test_integration.py."""
    # For generate methods, we check the structure rather than exact content
    assert "results" in actual_output, "Response missing 'results' key"
    assert len(actual_output["results"]) > 0, "Results list is empty"

    result = actual_output["results"][0]
    assert "sequences" in result, "Result missing 'sequences' key"

    # The number of sequences should match the request
    if expected_output is not None:
        expected_sequences = expected_output["results"][0]["sequences"]
        assert len(result["sequences"]) == len(
            expected_sequences
        ), "Number of sequences returned does not match expected"


test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={},  # Single variant model - applies to all
            test_cases=[
                # Integration tests with expected outputs
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=ENCODE_3HFM_INPUT,
                    expected_output_fixture=ENCODE_3HFM_OUTPUT,
                    tolerances={"rel_tol": 3e-4, "cosine_distance_threshold": 0.02},
                ),
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=ENCODE_8OI2_INPUT,
                    expected_output_fixture=ENCODE_8OI2_OUTPUT,
                    tolerances={"rel_tol": 3e-4, "cosine_distance_threshold": 0.02},
                ),
                ActionTestCase(
                    action_name=ModelActions.PREDICT_LOG_PROB,
                    input_fixture=LOGPROB_3HFM_INPUT,
                    expected_output_fixture=LOGPROB_3HFM_OUTPUT,
                    tolerances={"rel_tol": 1e-4},
                ),
                ActionTestCase(
                    action_name=ModelActions.SCORE,
                    input_fixture=LOGPROB_3HFM_INPUT,  # Uses same input as logprob
                    expected_output_fixture=SCORE_3HFM_OUTPUT,
                    tolerances={"rel_tol": 1e-4},
                ),
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=GENERATE_3HFM_INPUT,
                    expected_output_fixture=GENERATE_3HFM_OUTPUT,
                    validator=_validate_antifold_generate,
                ),
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=GENERATE_8OI2_INPUT,
                    expected_output_fixture=GENERATE_8OI2_OUTPUT,
                    validator=_validate_antifold_generate,
                ),
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=GENERATE_6Y1L_INPUT,
                    expected_output_fixture=GENERATE_6Y1L_OUTPUT,
                    validator=_validate_antifold_generate,
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
#   pytest models/antifold/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/antifold/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/antifold/test.py -n auto --no-cov -v -s                 # both
