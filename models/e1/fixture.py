from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.e1.config import MODEL_FAMILY
from models.e1.schema import (
    E1EncodeIncludeOptions,
    E1EncodeRequest,
    E1EncodeRequestItem,
    E1EncodeRequestParams,
    E1PredictRequest,
    E1PredictRequestItem,
)

# Input fixture filenames (shared across variants)
ENCODE_1_INPUT = "encode_1_input.json"
ENCODE_2_INPUT = "encode_2_input.json"
ENCODE_3_INPUT = "encode_3_input.json"  # With context sequences
PREDICT_INPUT = "predict_input.json"

# Output fixture templates (variant-specific)
ENCODE_1_OUTPUT_TPL = "{variant.name}_encode_1_expected_output.json"
ENCODE_2_OUTPUT_TPL = "{variant.name}_encode_2_expected_output.json"
ENCODE_3_OUTPUT_TPL = "{variant.name}_encode_3_expected_output.json"
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


def generate():
    """Configures and runs the fixture generator"""
    generator = FixtureGenerator(fixture_generation_suite)

    # Test Case 1: encode() with mean and logits
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.ENCODE,
            input_fixture=E1EncodeRequest(
                params=E1EncodeRequestParams(
                    include=[
                        E1EncodeIncludeOptions.MEAN,
                        E1EncodeIncludeOptions.LOGITS,
                    ]
                ),
                items=[
                    E1EncodeRequestItem(
                        sequence="TPSSKEMMSQALKATFSGFTKEQQRLGIPKDPRQWTETHVRDWVMWAVNEFSLKGVDFQKF"
                    )
                ],
            ),
            input_filename_template=ENCODE_1_INPUT,
            expected_output_fixture=ENCODE_1_OUTPUT_TPL,
        )
    )

    # Test Case 2: encode() with per-token embeddings
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.ENCODE,
            input_fixture=E1EncodeRequest(
                params=E1EncodeRequestParams(
                    include=[E1EncodeIncludeOptions.PER_TOKEN], repr_layers=[15]
                ),
                items=[
                    E1EncodeRequestItem(
                        sequence="TPSSKEMMSQALKATFSGFTKEQQRLGIPKDPRQWTETHVRDWVMWAVNEFSLKGVDFQKF"
                    )
                ],
            ),
            input_filename_template=ENCODE_2_INPUT,
            expected_output_fixture=ENCODE_2_OUTPUT_TPL,
        )
    )

    # Test Case 3: encode() with context sequences (retrieval-augmented mode)
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.ENCODE,
            input_fixture=E1EncodeRequest(
                params=E1EncodeRequestParams(
                    include=[
                        E1EncodeIncludeOptions.MEAN,
                    ]
                ),
                items=[
                    E1EncodeRequestItem(
                        sequence="TPSSKEMMSQALKATFSGFTKEQQRLGIPKDPRQWTETHVRDWVMWAVNEFSLKGVDFQKF",
                        context_sequences=[
                            "MPSSKEMMSQALKATFSGFTKEQQRLGIPKDPRQWTETHVRDWVMWAVNEFSLKGVDFQKL",
                            "TPSSKELMSQALKATFSGFTKEQQRLGIPKDPRQWTETHVRDWVMWAVNEFSLKGVDFQKY",
                        ],
                    )
                ],
            ),
            input_filename_template=ENCODE_3_INPUT,
            expected_output_fixture=ENCODE_3_OUTPUT_TPL,
        )
    )

    # Test Case 4: predict() with a masked sequence (uses '?' as mask token)
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=E1PredictRequest(
                items=[
                    E1PredictRequestItem(
                        sequence="MKAAVDLK?PFPSPDMECADVPLLTPSSKEMMSQALKATFSGFTKEQQRLGIPKDPRQWTETHVRDWVMWAVNEFSLKGVDFQKF"
                    )
                ]
            ),
            input_filename_template=PREDICT_INPUT,
            expected_output_fixture=PREDICT_OUTPUT_TPL,
        )
    )

    # Note: log_prob tests use validator-based approach in test.py
    # (no golden output fixtures needed - just validates log_prob is a float)

    generator.generate()


if __name__ == "__main__":
    #  python models/e1/fixture.py
    generate()
