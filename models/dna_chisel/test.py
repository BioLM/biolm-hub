from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.dna_chisel.config import MODEL_FAMILY
from models.dna_chisel.fixture import (
    DEFAULT_INPUT,
    DEFAULT_OUTPUT,
    EXPLICIT_INPUT,
    EXPLICIT_OUTPUT,
)

# DNA Chisel test suite
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={},  # Single variant model - applies to all
            test_cases=[
                # encode() with explicit parameters
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=EXPLICIT_INPUT,
                    expected_output_fixture=EXPLICIT_OUTPUT,
                    tolerances={"rel_tol": 1e-4},
                ),
                # encode() with default parameters
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=DEFAULT_INPUT,
                    expected_output_fixture=DEFAULT_OUTPUT,
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
#   pytest models/dna_chisel/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/dna_chisel/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/dna_chisel/test.py -n auto --no-cov -v -s                 # both
