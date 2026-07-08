from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.sadie.config import MODEL_FAMILY
from models.sadie.fixture import PREDICT_INPUT, PREDICT_OUTPUT

# SADIE test suite - single variant
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
                    input_fixture=PREDICT_INPUT,
                    expected_output_fixture=PREDICT_OUTPUT,
                    tolerances={"rel_tol": 1e-5},  # Tight tolerances for SADIE
                    request_schema=None,  # Send raw JSON - SADIE model uses Pydantic v1
                ),
            ],
        )
    ],
)

# Generate integration tests (marked with @pytest.mark.integration)
test_sadie_integration = generate_tests_from_suite(test_suite, test_type="integration")

# Generate deployment tests (marked with @pytest.mark.deployment)
test_sadie_deployment = generate_tests_from_suite(test_suite, test_type="deployment")

# Usage:
#   pytest models/sadie/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/sadie/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/sadie/test.py -n auto --no-cov -v -s                 # both
