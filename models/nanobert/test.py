from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import _validate_log_prob, generate_tests_from_suite
from models.nanobert.config import MODEL_FAMILY
from models.nanobert.fixture import (
    ENCODE_INPUT,
    ENCODE_OUTPUT,
    GENERATE_INPUT,
    GENERATE_OUTPUT,
)
from models.nanobert.schema import NanoBERTEncodeRequestItem, NanoBERTLogProbRequest

# NanoBERT test suite - single variant with multiple actions
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single mapping for the single variant
        VariantTestMapping(
            variant_config={},  # Empty dict for single-variant model
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=ENCODE_INPUT,
                    expected_output_fixture=ENCODE_OUTPUT,
                    tolerances={"rel_tol": 1e-4, "cosine_distance_threshold": 0.02},
                ),
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=GENERATE_INPUT,
                    expected_output_fixture=GENERATE_OUTPUT,
                    tolerances={"rel_tol": 1e-4},
                ),
                # Programmatic input for predict_log_prob
                ActionTestCase(
                    action_name=ModelActions.PREDICT_LOG_PROB,
                    input_fixture=NanoBERTLogProbRequest(
                        items=[
                            NanoBERTEncodeRequestItem(
                                sequence="QVQLVQSGAEVKKPGASVKVSCKVSGYTSPTTIHWVRQAPGKGLEWMGGISPYRGDTIYAQKFQGRVTMTEDTSTDTAYMELSSLKSEDTAVYYCARDGYSSGYYGMDVWGQGTTVTVSS"
                            ),
                            NanoBERTEncodeRequestItem(
                                sequence="QVQLVQSGAEVKKPGASVKVSCKVSGYPFTRSTIHWVRQAPGKGLEWMGGINAGTGDTIYAQKFQGRVTMTEDTSTDTAYMELSSLKSEDTAVYYCARDGYSSGYYGMDVWGQGTTVTVSS"
                            ),
                        ]
                    ),
                    validator=_validate_log_prob,
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
#   pytest models/nanobert/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/nanobert/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/nanobert/test.py -n auto --no-cov -v -s                 # both
