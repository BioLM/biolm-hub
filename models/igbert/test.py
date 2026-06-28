from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import _validate_log_prob, generate_tests_from_suite
from models.igbert.config import MODEL_FAMILY
from models.igbert.fixture import (
    PAIRED_ENCODE_INPUT,
    PAIRED_ENCODE_OUTPUT,
    PAIRED_GENERATE_INPUT,
    PAIRED_GENERATE_OUTPUT,
    UNPAIRED_ENCODE_INPUT,
    UNPAIRED_ENCODE_OUTPUT,
    UNPAIRED_GENERATE_INPUT,
    UNPAIRED_GENERATE_OUTPUT,
)


# Helper function to generate log prob input data based on model type
def _create_paired_logprob_input():
    return {
        "items": [
            {
                "heavy_chain": "QVQLVQSGAEVKKPGASVKVSCKVSGYTSPTTIHWVRQAPGKGLEWMGGISPYRGDTIYAQKFQGRVTMTEDTSTDTAYMELSSLKSEDTAVYYCARDGYSSGYYGMDVWGQGTTVTVSS",
                "light_chain": "DIQMTQSPSSVSASVGDRVTITCRASQSIGSFLAWYQQKPGKAPKLLIYEASTLKPGVPSRFSGSGSGTDFTLTISSLQPEDFANYYCHQYAAYPWTFGGGTKVEIK",
            },
            {
                "heavy_chain": "QVQLVQSGAEVKKPGASVKVSCKVSGYPFTRSTIHWVRQAPGKGLEWMGGINAGTGDTIYAQKFQGRVTMTEDTSTDTAYMELSSLKSEDTAVYYCARDGYSSGYYGMDVWGQGTTVTVSS",
                "light_chain": "DIQMTQSPSSVSASVGDRVTITCRASQNIHSYLAWYQQKPGKAPKLLIYDASILASGVPSRFSGSGSGTDFTLTISSLQPEDFANYYCQQYSTHSWTFGGGTKVEIK",
            },
        ]
    }


def _create_unpaired_logprob_input():
    return {
        "items": [
            {
                "sequence": "QVQLVQSGAEVKKPGASVKVSCKVSGYTSPTTIHWVRQAPGKGLEWMGGISPYRGDTIYAQKFQGRVTMTEDTSTDTAYMELSSLKSEDTAVYYCARDGYSSGYYGMDVWGQGTTVTVSS"
            },
            {
                "sequence": "QVQLVQSGAEVKKPGASVKVSCKVSGYPFTRSTIHWVRQAPGKGLEWMGGINAGTGDTIYAQKFQGRVTMTEDTSTDTAYMELSSLKSEDTAVYYCARDGYSSGYYGMDVWGQGTTVTVSS"
            },
        ]
    }


# IgBert test suite - variant-specific test mappings based on model type
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Paired model variant
        VariantTestMapping(
            variant_config={"MODEL_TYPE": "paired"},
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=PAIRED_ENCODE_INPUT,
                    expected_output_fixture=PAIRED_ENCODE_OUTPUT,
                    tolerances={"rel_tol": 1e-4},
                ),
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=PAIRED_GENERATE_INPUT,
                    expected_output_fixture=PAIRED_GENERATE_OUTPUT,
                    tolerances={"rel_tol": 1e-4},
                ),
                ActionTestCase(
                    action_name=ModelActions.LOG_PROB,
                    input_fixture=_create_paired_logprob_input(),
                    validator=_validate_log_prob,
                ),
            ],
        ),
        # Unpaired model variant
        VariantTestMapping(
            variant_config={"MODEL_TYPE": "unpaired"},
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=UNPAIRED_ENCODE_INPUT,
                    expected_output_fixture=UNPAIRED_ENCODE_OUTPUT,
                    tolerances={"rel_tol": 1e-4},
                ),
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=UNPAIRED_GENERATE_INPUT,
                    expected_output_fixture=UNPAIRED_GENERATE_OUTPUT,
                    tolerances={"rel_tol": 1e-4},
                ),
                ActionTestCase(
                    action_name=ModelActions.LOG_PROB,
                    input_fixture=_create_unpaired_logprob_input(),
                    validator=_validate_log_prob,
                ),
            ],
        ),
    ],
)

# Generate integration tests (marked with @pytest.mark.integration)
test_igbert_integration = generate_tests_from_suite(test_suite, test_type="integration")

# Generate deployment tests (marked with @pytest.mark.deployment)
test_igbert_deployment = generate_tests_from_suite(test_suite, test_type="deployment")

# Usage:
#   pytest models/igbert/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/igbert/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/igbert/test.py -n auto --no-cov -v -s                 # both
