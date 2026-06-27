from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import _validate_log_prob, generate_tests_from_suite
from models.esm1b.config import MODEL_FAMILY
from models.esm1b.fixture import (
    MASKED_INPUT,
    MASKED_PREDICT_OUTPUT,
    MULTIPLE_ENCODE_OUTPUT,
    MULTIPLE_SEQS_INPUT,
    SINGLE_ENCODE_OUTPUT,
    SINGLE_SEQ_INPUT,
)

# ESM-1b test suite - single variant, multiple actions
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single mapping for the single variant
        VariantTestMapping(
            variant_config={},  # Empty dict - single variant
            test_cases=[
                # Encode action - single sequence
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=SINGLE_SEQ_INPUT,  # String path
                    expected_output_fixture=SINGLE_ENCODE_OUTPUT,
                    tolerances={"rel_tol": 1e-4, "cosine_distance_threshold": 0.02},
                ),
                # Encode action - multiple sequences
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=MULTIPLE_SEQS_INPUT,  # String path
                    expected_output_fixture=MULTIPLE_ENCODE_OUTPUT,
                    tolerances={"rel_tol": 1e-4, "cosine_distance_threshold": 0.02},
                ),
                # Predict action - masked sequence
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=MASKED_INPUT,  # String path
                    expected_output_fixture=MASKED_PREDICT_OUTPUT,
                    tolerances={"rel_tol": 1e-4, "cosine_distance_threshold": 0.02},
                ),
                # Predict log prob action with programmatic input
                ActionTestCase(
                    action_name=ModelActions.LOG_PROB,
                    # Programmatic input - create data on the fly
                    input_fixture={
                        "items": [
                            {
                                "sequence": "TPSSKEMMSQALKATFSGFTKEQQRLGIPKDPRQWTETHVRDWVMWAVNEFSLKGVDFQKF"
                            }
                        ]
                    },
                    # Use shared validator from commons
                    validator=_validate_log_prob,
                ),
            ],
        )
    ],
)

# Generate integration tests (marked with @pytest.mark.integration)
test_esm1b_integration = generate_tests_from_suite(test_suite, test_type="integration")

# Generate deployment tests (marked with @pytest.mark.deployment)
test_esm1b_deployment = generate_tests_from_suite(test_suite, test_type="deployment")

# Usage:
#   pytest models/esm1b/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/esm1b/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/esm1b/test.py -n auto --no-cov -v -s                 # both
