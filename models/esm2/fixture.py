from models.commons.model.schema import ModelActions
from models.commons.storage.r2 import read_json_from_r2
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.commons.util.config import r2_bucket_name, r2_test_data_dir
from models.esm2.config import MODEL_FAMILY, ESM2ModelSizes
from models.esm2.schema import ESM2EncodeRequest, ESM2Params, ESM2PredictRequest

# Legacy string paths for manually generated fixtures (8m, 35m, 150m, 650m)
# These are used in test.py for the old approach
SINGLE_SEQ_INPUT = "single_seq_input.json"
MULTIPLE_SEQS_INPUT = "multiple_seqs_input.json"
MASKED_INPUT = "masked_input.json"
SINGLE_ENCODE_OUTPUT_TPL = "{variant.name}_single_encode_expected_output.json"
MULTIPLE_ENCODE_OUTPUT_TPL = "{variant.name}_multiple_encode_expected_output.json"
MASKED_PREDICT_OUTPUT_TPL = "{variant.name}_masked_predict_expected_output.json"

# Load test inputs from R2 at module level for programmatic fixture generation
base_path = f"{r2_test_data_dir}/models/{ESM2Params.base_model_slug}"
single_seq_data = read_json_from_r2(r2_bucket_name, f"{base_path}/{SINGLE_SEQ_INPUT}")
multiple_seqs_data = read_json_from_r2(
    r2_bucket_name, f"{base_path}/{MULTIPLE_SEQS_INPUT}"
)
masked_data = read_json_from_r2(r2_bucket_name, f"{base_path}/{MASKED_INPUT}")

# Convert dicts to Pydantic objects using model_validate
single_seq_request = ESM2EncodeRequest.model_validate(single_seq_data)
multiple_seqs_request = ESM2EncodeRequest.model_validate(multiple_seqs_data)
masked_request = ESM2PredictRequest.model_validate(masked_data)

# TestSuite for fixture generation - configured for 3B variant only
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={
                "MODEL_SIZE": ESM2ModelSizes.SIZE_3B
            },  # Only matches 3B variant
            test_cases=[
                # Test Case 1: Single sequence encode
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=single_seq_request,
                    input_filename_template=SINGLE_SEQ_INPUT,
                    expected_output_fixture=SINGLE_ENCODE_OUTPUT_TPL,
                ),
                # Test Case 2: Multiple sequences encode with params
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=multiple_seqs_request,
                    input_filename_template=MULTIPLE_SEQS_INPUT,
                    expected_output_fixture=MULTIPLE_ENCODE_OUTPUT_TPL,
                ),
                # Test Case 3: Masked sequence predict
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=masked_request,
                    input_filename_template=MASKED_INPUT,
                    expected_output_fixture=MASKED_PREDICT_OUTPUT_TPL,
                ),
            ],
        )
    ],
)


def generate():
    """Configures and runs the fixture generator for ESM2-3B variant"""
    generator = FixtureGenerator(fixture_generation_suite)
    # Test cases are now in the TestSuite, respecting variant filtering
    generator.generate()


if __name__ == "__main__":
    generate()

# Run with: python models/esm2/fixture.py
