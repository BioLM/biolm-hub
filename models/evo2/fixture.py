from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.evo2.config import MODEL_FAMILY
from models.evo2.schema import (
    Evo2EncodeIncludeOptions,
    Evo2EncodeRequest,
    Evo2EncodeRequestItem,
    Evo2EncodeRequestParams,
    Evo2GenerateRequest,
    Evo2GenerateRequestItem,
    Evo2GenerateRequestParams,
    Evo2LogProbRequest,
    Evo2LogProbRequestItem,
)

ENCODE_INPUT = "encode_input.json"
LOGPROB_INPUT = "logprob_input.json"
GENERATE_INPUT = "generate_input.json"
ENCODE_OUTPUT_TPL = "{variant.name}_encode_expected_output.json"
LOGPROB_OUTPUT_TPL = "{variant.name}_logprob_expected_output.json"
GENERATE_OUTPUT_TPL = "{variant.name}_generate_expected_output.json"


# Create TestSuite for fixture generation with programmatic inputs
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single mapping that applies to ALL variants
        VariantTestMapping(
            variant_config={},  # Empty dict means applies to ALL variants
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
            input_fixture=Evo2EncodeRequest(
                params=Evo2EncodeRequestParams(
                    embedding_layers=[22],
                    include=[
                        Evo2EncodeIncludeOptions.MEAN,
                        Evo2EncodeIncludeOptions.LAST,
                    ],
                ),
                items=[Evo2EncodeRequestItem(sequence="ACGTACGTAC")],
            ),
            input_filename_template=ENCODE_INPUT,
            expected_output_fixture=ENCODE_OUTPUT_TPL,
        )
    )

    # Test Case 2: log_prob()
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.LOG_PROB,
            input_fixture=Evo2LogProbRequest(
                items=[
                    Evo2LogProbRequestItem(sequence="ACGTACGTAC"),
                ]
            ),
            input_filename_template=LOGPROB_INPUT,
            expected_output_fixture=LOGPROB_OUTPUT_TPL,
        )
    )

    # Test Case 3: generate()
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.GENERATE,
            input_fixture=Evo2GenerateRequest(
                params=Evo2GenerateRequestParams(
                    max_new_tokens=10,
                    temperature=1.0,
                    top_k=4,
                    top_p=1.0,
                ),
                items=[
                    Evo2GenerateRequestItem(
                        prompt="ACGT",
                    )
                ],
            ),
            input_filename_template=GENERATE_INPUT,
            expected_output_fixture=GENERATE_OUTPUT_TPL,
        )
    )

    generator.generate()


if __name__ == "__main__":
    generate()
