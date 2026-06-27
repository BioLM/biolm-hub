from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.esm_if1.config import MODEL_FAMILY
from models.esm_if1.fixture import (
    GENERATE_INPUT,
    GENERATE_OUTPUT,
)

# ESM-IF1 test suite - single variant model with one action
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single mapping that applies to the single variant
        VariantTestMapping(
            variant_config={},  # Empty dict means applies to ALL variants (only one in this case)
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=GENERATE_INPUT,
                    expected_output_fixture=GENERATE_OUTPUT,
                    tolerances={
                        "rel_tol": 0.5,
                        "is_generated_seq": True,
                    },
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
#   pytest models/esm_if1/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/esm_if1/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/esm_if1/test.py -n auto --no-cov -v -s                 # both
