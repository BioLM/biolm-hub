from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.evo.config import MODEL_FAMILY
from models.evo.schema import (
    EvoGenerateRequest,
    EvoGenerateRequestItem,
    EvoPredictLogProbRequest,
    EvoPredictLogProbRequestItem,
)

LOGPROB_INPUT = "logprob_input.json"
LOGPROB_OUTPUT = "logprob_expected_output.json"
GENERATE_INPUT = "generate_input.json"
GENERATE_OUTPUT = "generate_expected_output.json"

# Create TestSuite for fixture generation with programmatic inputs
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single mapping for the single variant
        VariantTestMapping(
            variant_config={},  # Empty dict for single-variant model
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.LOG_PROB,
                    input_filename_template=LOGPROB_INPUT,
                    # Programmatic input - will be written as logprob_input.json
                    input_fixture=EvoPredictLogProbRequest(
                        items=[
                            EvoPredictLogProbRequestItem(sequence="ACGTAC"),
                            EvoPredictLogProbRequestItem(sequence="ACGTACGTAC"),
                        ]
                    ),
                    expected_output_fixture=LOGPROB_OUTPUT,
                ),
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_filename_template=GENERATE_INPUT,
                    # Programmatic input - will be written as generate_input.json
                    input_fixture=EvoGenerateRequest(
                        items=[
                            EvoGenerateRequestItem(prompt="ACGT"),
                        ]
                    ),
                    expected_output_fixture=GENERATE_OUTPUT,
                ),
            ],
        )
    ],
)


def generate():
    """Configures and runs the fixture generator"""
    generator = FixtureGenerator(fixture_generation_suite)
    generator.generate()


if __name__ == "__main__":
    generate()
