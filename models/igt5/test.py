from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.igt5.config import MODEL_FAMILY
from models.igt5.fixture import ENCODE_INPUT_TPL, ENCODE_OUTPUT_TPL

# IgT5 test suite - all variants use the same test pattern
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single mapping that applies to ALL variants
        VariantTestMapping(
            variant_config={},  # Empty dict means applies to ALL variants
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=ENCODE_INPUT_TPL,
                    expected_output_fixture=ENCODE_OUTPUT_TPL,
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
#   pytest models/igt5/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/igt5/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/igt5/test.py -n auto --no-cov -v -s                 # both
