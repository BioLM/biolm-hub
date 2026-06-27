from models.ablang2.config import MODEL_FAMILY
from models.ablang2.fixture import (
    ENCODE_RESCODING_INPUT,
    ENCODE_RESCODING_OUTPUT,
    ENCODE_SEQCODING_INPUT,
    ENCODE_SEQCODING_OUTPUT,
    GENERATE_INPUT,
    GENERATE_OUTPUT,
    PREDICT_INPUT,
    PREDICT_OUTPUT,
)
from models.ablang2.schema import AbLang2LogProbRequest
from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import _validate_log_prob, generate_tests_from_suite

test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={},  # Applies to all variants
            test_cases=[
                # encode – SEQCODING
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=ENCODE_SEQCODING_INPUT,
                    expected_output_fixture=ENCODE_SEQCODING_OUTPUT,
                    tolerances={"rel_tol": 1e-4, "cosine_distance_threshold": 0.02},
                ),
                # encode – RESCODING
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=ENCODE_RESCODING_INPUT,
                    expected_output_fixture=ENCODE_RESCODING_OUTPUT,
                    tolerances={"rel_tol": 1e-4, "cosine_distance_threshold": 0.02},
                ),
                # predict
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=PREDICT_INPUT,
                    expected_output_fixture=PREDICT_OUTPUT,
                    tolerances={"rel_tol": 1e-4, "cosine_distance_threshold": 0.02},
                ),
                # generate
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=GENERATE_INPUT,
                    expected_output_fixture=GENERATE_OUTPUT,
                    tolerances={"rel_tol": 1e-4},
                ),
                # predict_log_prob (programmatic)
                ActionTestCase(
                    action_name=ModelActions.PREDICT_LOG_PROB,
                    input_fixture=AbLang2LogProbRequest(
                        items=[
                            {
                                "heavy": "QVQLVQSGGQMKKPGSSVRVSCKASGYTFTNYGMNWVRQAPGQGLEWMGRI",
                                "light": "DIQMTQSPSSLSASVGDRVTITCKASQDVSTAVA",
                            }
                        ]
                    ),
                    request_schema=AbLang2LogProbRequest,
                    validator=_validate_log_prob,
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
#   pytest models/ablang2/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/ablang2/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/ablang2/test.py -n auto --no-cov -v -s                 # both
