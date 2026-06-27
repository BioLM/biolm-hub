from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.dnabert2.config import MODEL_FAMILY
from models.dnabert2.schema import (
    DNABERT2EncodeRequest,
    DNABERT2EncodeRequestItem,
    DNABERT2PredictLogProbRequest,
    DNABERT2PredictLogProbRequestItem,
)

ENCODE_INPUT = "encode_input.json"
ENCODE_OUTPUT = "encode_expected_output.json"
LOGPROB_INPUT = "logprob_input.json"
LOGPROB_OUTPUT = "logprob_expected_output.json"


# Create TestSuite for fixture generation with programmatic inputs
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single mapping for the single variant
        VariantTestMapping(
            variant_config={},  # Empty dict for single-variant model
            test_cases=[
                # Test cases will be added by the generate() function
            ],
        )
    ],
)


def generate():
    """Configures and runs the fixture generator"""
    generator = FixtureGenerator(fixture_generation_suite)

    # Test Case 1: encode()
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.ENCODE,
            input_fixture=DNABERT2EncodeRequest(
                items=[
                    DNABERT2EncodeRequestItem(sequence="ACGTACGT"),
                ]
            ),
            input_filename_template=ENCODE_INPUT,
            expected_output_fixture=ENCODE_OUTPUT,
        )
    )

    # Test Case 2: predict_log_prob()
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.PREDICT_LOG_PROB,
            input_fixture=DNABERT2PredictLogProbRequest(
                items=[
                    DNABERT2PredictLogProbRequestItem(sequence="ACGT"),
                    DNABERT2PredictLogProbRequestItem(sequence="ACGTACGT"),
                ]
            ),
            input_filename_template=LOGPROB_INPUT,
            expected_output_fixture=LOGPROB_OUTPUT,
        )
    )

    generator.generate()


if __name__ == "__main__":
    generate()
