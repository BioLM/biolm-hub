from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.commons.testing.shared_assets import STANDARD_PROTEIN
from models.esmc.config import MODEL_FAMILY
from models.esmc.schema import (
    ESMCEncodeIncludeOptions,
    ESMCEncodeRequest,
    ESMCEncodeRequestItem,
    ESMCEncodeRequestParams,
    ESMCPredictRequest,
    ESMCPredictRequestItem,
)

ENCODE_1_INPUT = "encode_1_input.json"
ENCODE_2_INPUT = "encode_2_input.json"
PREDICT_INPUT = "predict_input.json"
ENCODE_1_OUTPUT_TPL = "{variant.name}_encode_1_expected_output.json"
ENCODE_2_OUTPUT_TPL = "{variant.name}_encode_2_expected_output.json"
PREDICT_OUTPUT_TPL = "{variant.name}_predict_expected_output.json"


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


def generate() -> None:
    """Configures and runs the fixture generator"""
    generator = FixtureGenerator(fixture_generation_suite)

    # Test Case 1: encode() with mean/logits
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.ENCODE,
            input_fixture=ESMCEncodeRequest(
                params=ESMCEncodeRequestParams(
                    include=[
                        ESMCEncodeIncludeOptions.MEAN,
                        ESMCEncodeIncludeOptions.LOGITS,
                    ]
                ),
                items=[ESMCEncodeRequestItem(sequence=STANDARD_PROTEIN)],
            ),
            input_filename_template=ENCODE_1_INPUT,
            expected_output_fixture=ENCODE_1_OUTPUT_TPL,
        )
    )

    # Test Case 2: encode() with per-token embeddings
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.ENCODE,
            input_fixture=ESMCEncodeRequest(
                params=ESMCEncodeRequestParams(
                    include=[ESMCEncodeIncludeOptions.PER_TOKEN], repr_layers=[15]
                ),
                items=[ESMCEncodeRequestItem(sequence=STANDARD_PROTEIN)],
            ),
            input_filename_template=ENCODE_2_INPUT,
            expected_output_fixture=ENCODE_2_OUTPUT_TPL,
        )
    )

    # Test Case 3: predict() with a masked sequence
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=ESMCPredictRequest(
                items=[
                    ESMCPredictRequestItem(
                        sequence="MKAAVDLK<mask>PFPSPDMECADVPLLTPSSKEMMSQALKATFSGFTKEQQRLGIPKDPRQWTETHVRDWVMWAVNEFSLKGVDFQKF"
                    )
                ]
            ),
            input_filename_template=PREDICT_INPUT,
            expected_output_fixture=PREDICT_OUTPUT_TPL,
        )
    )

    generator.generate()


if __name__ == "__main__":
    # python models/esmc/fixture.py
    generate()
