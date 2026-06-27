from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.msa_transformer.config import MODEL_FAMILY
from models.msa_transformer.fixture import (
    BATCH_MSA_ENCODE_OUTPUT,
    BATCH_MSA_INPUT,
    PER_TOKEN_INPUT,
    PER_TOKEN_OUTPUT,
    ROW_ATTENTION_INPUT,
    ROW_ATTENTION_OUTPUT,
    SINGLE_MSA_ENCODE_OUTPUT,
    SINGLE_MSA_INPUT,
)

# MSA Transformer test suite - single variant, multiple test cases
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single mapping for the single variant
        VariantTestMapping(
            variant_config={},  # Empty dict for single variant
            test_cases=[
                # Single MSA encode test
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=SINGLE_MSA_INPUT,
                    expected_output_fixture=SINGLE_MSA_ENCODE_OUTPUT,
                    tolerances={"rel_tol": 1e-4, "cosine_distance_threshold": 0.02},
                ),
                # Batch MSA encode test
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=BATCH_MSA_INPUT,
                    expected_output_fixture=BATCH_MSA_ENCODE_OUTPUT,
                    tolerances={"rel_tol": 1e-4, "cosine_distance_threshold": 0.02},
                ),
                # Row attention test
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=ROW_ATTENTION_INPUT,
                    expected_output_fixture=ROW_ATTENTION_OUTPUT,
                    tolerances={"rel_tol": 1e-4, "cosine_distance_threshold": 0.02},
                ),
                # Per-token embeddings test
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=PER_TOKEN_INPUT,
                    expected_output_fixture=PER_TOKEN_OUTPUT,
                    tolerances={"rel_tol": 1e-4, "cosine_distance_threshold": 0.02},
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
#   pytest models/msa_transformer/test.py -m integration -n auto --no-cov -v -s
#   pytest models/msa_transformer/test.py -m deployment -n auto --no-cov -v -s
#   pytest models/msa_transformer/test.py -n auto --no-cov -v -s
