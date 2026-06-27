from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.temberture.config import MODEL_FAMILY
from models.temberture.schema import (
    TemBERTureEncodeIncludeOptions,
    TemBERTureEncodeRequest,
    TemBERTureEncodeRequestItem,
    TemBERTureEncodeRequestParams,
    TemBERTurePredictRequest,
    TemBERTurePredictRequestItem,
)

# Fixture filename constants
ENCODE_INPUT = "encode_input.json"
PREDICT_INPUT = "predict_input.json"
ENCODE_OUTPUT_TPL = "{variant.name}_encode_expected_output.json"
PREDICT_OUTPUT_TPL = "{variant.name}_predict_expected_output.json"

# Test sequences
SEQUENCE_1 = "MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVLAGG"
SEQUENCE_2 = "MEKVYGLIGFPVEHSLSPLMHNDAFARLGIPARYHLFSVEPGQVGAAIAGVRALGIAGVNVTIPHKLAVIPFLDEVDEHARRIGAVNTIINNDGRLIGFNTDGPGYVQALEEEMNITLDGKRILVIGAGGGARGIYFSLLSTAAERIDMANRTVEKAERLVREGEGGRSAYFSLAEAETRLDEYDIIINTTSVGMHPRVEVQPLSLERLRPGVIVSNIIYNPLETKWLKEAKARGARVQNGVGMLVYQGALAFEKWTGQWPDVNRMKQLVIEALRR"

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

    # Test Case 1: encode() with multiple embedding types
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.ENCODE,
            input_fixture=TemBERTureEncodeRequest(
                params=TemBERTureEncodeRequestParams(
                    include=[
                        TemBERTureEncodeIncludeOptions.MEAN,
                        TemBERTureEncodeIncludeOptions.PER_RESIDUE,
                        TemBERTureEncodeIncludeOptions.CLS,
                    ]
                ),
                items=[
                    TemBERTureEncodeRequestItem(sequence=SEQUENCE_1),
                    TemBERTureEncodeRequestItem(sequence=SEQUENCE_2),
                ],
            ),
            input_filename_template=ENCODE_INPUT,
            expected_output_fixture=ENCODE_OUTPUT_TPL,
        )
    )

    # Test Case 2: predict() with sequences
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=TemBERTurePredictRequest(
                items=[
                    TemBERTurePredictRequestItem(sequence=SEQUENCE_1),
                    TemBERTurePredictRequestItem(sequence=SEQUENCE_2),
                ]
            ),
            input_filename_template=PREDICT_INPUT,
            expected_output_fixture=PREDICT_OUTPUT_TPL,
        )
    )

    generator.generate()


if __name__ == "__main__":
    generate()
