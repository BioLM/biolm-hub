from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.dummy.config import MODEL_FAMILY
from models.dummy.schema import DummySvcRequest


def _validate_dummy_predict(actual_output: dict, _expected_output: dict = None):
    """Custom validator for dummy model output."""
    expected_output = {
        "results": [
            {
                "dummy_svc_resp_field": "test_input_processed_by_dummy_model",
                "data_file_content": "world",  # This should match the content in dummy_test_data.json
            }
        ]
    }
    assert actual_output == expected_output, "Prediction test failed"


# Dummy test suite - single variant with programmatic input
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single mapping for the single variant
        VariantTestMapping(
            variant_config={},  # Empty dict for single variant
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    # Programmatic input - create data on the fly
                    input_fixture=DummySvcRequest.model_validate(
                        {
                            "items": [
                                {
                                    "dummy_model_input_field": "test_input",
                                }
                            ]
                        }
                    ),
                    # Use custom validator
                    validator=_validate_dummy_predict,
                    remote_fn_kwargs={"_skip_cache": True},
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
#   pytest models/dummy/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/dummy/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/dummy/test.py -n auto --no-cov -v -s                 # both
