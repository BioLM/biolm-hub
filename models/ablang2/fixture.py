from models.ablang2.config import MODEL_FAMILY
from models.ablang2.schema import (
    AbLang2EncodeOptions,
    AbLang2EncodeParams,
    AbLang2EncodeRequest,
    AbLang2GenerateRequest,
    AbLang2MissingSequenceItem,
    AbLang2PredictRequest,
    AbLang2RestoreParams,
    AbLang2SequenceItem,
)
from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator

ENCODE_SEQCODING_INPUT = "encode_1_input.json"
ENCODE_SEQCODING_OUTPUT = "encode_1_expected_output.json"
ENCODE_RESCODING_INPUT = "encode_2_input.json"
ENCODE_RESCODING_OUTPUT = "encode_2_expected_output.json"
PREDICT_INPUT = "predict_input.json"
PREDICT_OUTPUT = "predict_expected_output.json"
GENERATE_INPUT = "generate_input.json"
GENERATE_OUTPUT = "generate_expected_output.json"

# Canonical test antibody pair — shared across tests to prevent drift
SEQ_1 = AbLang2SequenceItem(
    heavy_chain="QVQLVQSGGQMKKPGSSVRVSCKASGYTFTNYGMNWVRQAPGQGLEWMGRI",
    light_chain="DIQMTQSPSSLSASVGDRVTITCKASQDVSTAVA",
)


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

    # Define common input data (seq_1 is the module-level SEQ_1 constant)
    seq_1 = SEQ_1
    seq_2 = AbLang2SequenceItem(
        heavy_chain="EVQLVESGGGLVKPGGSLKLSCAASGFTFSSYAMNWVRQAPGKGLEWVASIL",
        light_chain="DVVMTQTPLSLPVSLGDQASISCRSSQSLVHSNGNTYLHW",
    )

    # Test Case 1: encode() with SEQCODING
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.ENCODE,
            input_fixture=AbLang2EncodeRequest(
                params=AbLang2EncodeParams(include=AbLang2EncodeOptions.SEQCODING),
                items=[seq_1, seq_2],
            ),
            input_filename_template=ENCODE_SEQCODING_INPUT,
            expected_output_fixture=ENCODE_SEQCODING_OUTPUT,
        )
    )

    # Test Case 2: encode() with RESCODING
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.ENCODE,
            input_fixture=AbLang2EncodeRequest(
                params=AbLang2EncodeParams(include=AbLang2EncodeOptions.RESCODING),
                items=[seq_1],
            ),
            input_filename_template=ENCODE_RESCODING_INPUT,
            expected_output_fixture=ENCODE_RESCODING_OUTPUT,
        )
    )

    # Test Case 3: predict()
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=AbLang2PredictRequest(items=[seq_1]),
            input_filename_template=PREDICT_INPUT,
            expected_output_fixture=PREDICT_OUTPUT,
        )
    )

    # Test Case 4: generate()
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.GENERATE,
            input_fixture=AbLang2GenerateRequest(
                params=AbLang2RestoreParams(align=False),
                items=[
                    AbLang2MissingSequenceItem(
                        heavy_chain="QVQLVQ*GGQMKKPGSSVRVSCKASGYTFTNYGMN**VRQAPGQGLEWMGRI",
                        light_chain="DIQMTQSPSSLSA*VGDRVTITCKASQDVSTAVA",
                    )
                ],
            ),
            input_filename_template=GENERATE_INPUT,
            expected_output_fixture=GENERATE_OUTPUT,
        )
    )

    generator.generate()


if __name__ == "__main__":
    generate()
