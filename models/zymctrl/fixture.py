from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.zymctrl.config import MODEL_FAMILY
from models.zymctrl.schema import (
    ZymCTRLEncodeParams,
    ZymCTRLEncodeRequest,
    ZymCTRLEncodeRequestItem,
    ZymCTRLGenerateParams,
    ZymCTRLGenerateRequest,
    ZymCTRLGenerateRequestItem,
    ZymCTRLPoolingType,
)

# Input/output filenames for tests
GENERATE_INPUT = "generate_input.json"
GENERATE_OUTPUT = "generate_expected_output.json"
ENCODE_INPUT = "encode_input.json"
ENCODE_OUTPUT = "encode_expected_output.json"

# Create TestSuite for fixture generation with programmatic inputs
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single variant - empty dict means applies to all
        VariantTestMapping(
            variant_config={},
            test_cases=[],  # Test cases added by generate()
        )
    ],
)


def generate():
    """Configures and runs the fixture generator for ZymCTRL."""
    generator = FixtureGenerator(fixture_generation_suite)

    # Test Case 1: generate() - Generate enzyme sequences for an EC number
    # Using EC 3.5.5.1 (adenosylhomocysteinase) as test case
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.GENERATE,
            input_fixture=ZymCTRLGenerateRequest(
                params=ZymCTRLGenerateParams(
                    temperature=0.8,
                    top_k=9,
                    repetition_penalty=1.2,
                    num_samples=2,  # Generate 2 samples for testing
                    max_length=100,  # Shorter for faster tests
                ),
                items=[
                    ZymCTRLGenerateRequestItem(ec_number="3.5.5.1"),
                ],
            ),
            input_filename_template=GENERATE_INPUT,
            expected_output_fixture=GENERATE_OUTPUT,
        )
    )

    # Test Case 2: encode() - Extract embeddings with mean pooling
    # Using a short enzyme sequence fragment
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.ENCODE,
            input_fixture=ZymCTRLEncodeRequest(
                params=ZymCTRLEncodeParams(
                    pooling=ZymCTRLPoolingType.MEAN,
                    layer=-1,  # Last layer
                ),
                items=[
                    ZymCTRLEncodeRequestItem(
                        sequence="MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDI",
                        ec_number="3.5.5.1",  # Optional EC context
                    ),
                ],
            ),
            input_filename_template=ENCODE_INPUT,
            expected_output_fixture=ENCODE_OUTPUT,
        )
    )

    generator.generate()


if __name__ == "__main__":
    # python models/zymctrl/fixture.py
    generate()
