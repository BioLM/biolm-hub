from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.evo.config import MODEL_FAMILY
from models.evo.fixture import (
    GENERATE_INPUT,
    GENERATE_OUTPUT,
    LOGPROB_INPUT,
    LOGPROB_OUTPUT,
)

# Evo test suite - multi-variant model (currently 1 variant enabled) with two actions
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single mapping that applies to ALL variants
        VariantTestMapping(
            variant_config={},  # Empty dict means applies to ALL variants
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.LOG_PROB,
                    input_fixture=LOGPROB_INPUT,
                    expected_output_fixture=LOGPROB_OUTPUT,
                    tolerances={"rel_tol": 1e-4},
                ),
                # is_generated_seq compares length only, NOT the residues — deliberate:
                # Evo GENERATES sequences by autoregressive sampling, so the exact bases
                # differ run to run and a numeric golden comparison would be meaningless.
                # The golden pins the expected length instead. (The LOG_PROB case above
                # IS a real numeric comparison — log-probabilities are deterministic.)
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=GENERATE_INPUT,
                    expected_output_fixture=GENERATE_OUTPUT,
                    tolerances={"is_generated_seq": True},
                ),
            ],
        )
    ],
)

# Generate integration tests (marked with @pytest.mark.integration)
test_evo_integration = generate_tests_from_suite(test_suite, test_type="integration")

# Generate deployment tests (marked with @pytest.mark.deployment)
test_evo_deployment = generate_tests_from_suite(test_suite, test_type="deployment")

# Usage:
#   pytest models/evo/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/evo/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/evo/test.py -n auto --no-cov -v -s                 # both
