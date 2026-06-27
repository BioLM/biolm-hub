from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.esm1v.config import MODEL_FAMILY
from models.esm1v.fixture import PREDICT_INPUT, PREDICT_OUTPUT_TPL

# ESM1v test suite - all variants use the same input, different expected outputs
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single mapping that applies to ALL variants
        VariantTestMapping(
            variant_config={},  # Empty dict means applies to ALL variants
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=PREDICT_INPUT,
                    # Template: will be formatted with variant.name (e.g., "n1_predict_expected_output.json")
                    expected_output_fixture=PREDICT_OUTPUT_TPL,
                    tolerances={"rel_tol": 1e-4},
                ),
            ],
        )
    ],
)

# Generate integration tests (marked with @pytest.mark.integration)
test_esm1v_integration = generate_tests_from_suite(test_suite, test_type="integration")

# Generate deployment tests (marked with @pytest.mark.deployment)
test_esm1v_deployment = generate_tests_from_suite(test_suite, test_type="deployment")

# Usage:
#   pytest models/esm1v/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/esm1v/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/esm1v/test.py -n auto --no-cov -v -s                 # both
