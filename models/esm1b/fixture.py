from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.commons.testing.shared_assets import STANDARD_PROTEIN
from models.esm1b.config import MODEL_FAMILY
from models.esm1b.schema import (
    ESM1bEncodeRequest,
    ESM1bEncodeRequestItem,
    ESM1bEncodeRequestParams,
    ESM1bPredictRequest,
    ESM1bPredictRequestItem,
)

# File path constants for test fixtures
# Single-variant model - no template variables needed
SINGLE_SEQ_INPUT = "single_seq_input.json"
MULTIPLE_SEQS_INPUT = "multiple_seqs_input.json"
MASKED_INPUT = "masked_input.json"
SINGLE_ENCODE_OUTPUT = "single_encode_expected_output.json"
MULTIPLE_ENCODE_OUTPUT = "multiple_encode_expected_output.json"
MASKED_PREDICT_OUTPUT = "masked_predict_expected_output.json"

# Test sequences (standard protein sequences)
TEST_SEQUENCE_SHORT = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAV"
TEST_SEQUENCE_MEDIUM = STANDARD_PROTEIN
TEST_SEQUENCES_MULTIPLE = [TEST_SEQUENCE_SHORT, TEST_SEQUENCE_MEDIUM]
TEST_SEQUENCE_MASKED = "MKTAYIAK<mask>RQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAV"

# Create Pydantic request objects for fixture generation
single_seq_request = ESM1bEncodeRequest(
    params=ESM1bEncodeRequestParams(),
    items=[ESM1bEncodeRequestItem(sequence=TEST_SEQUENCE_SHORT)],
)

multiple_seqs_request = ESM1bEncodeRequest(
    params=ESM1bEncodeRequestParams(),
    items=[ESM1bEncodeRequestItem(sequence=seq) for seq in TEST_SEQUENCES_MULTIPLE],
)

masked_request = ESM1bPredictRequest(
    items=[ESM1bPredictRequestItem(sequence=TEST_SEQUENCE_MASKED)],
)


# TestSuite for fixture generation
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={},  # Single variant - empty config
            test_cases=[
                # Test Case 1: Single sequence encode
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=single_seq_request,
                    input_filename_template=SINGLE_SEQ_INPUT,
                    expected_output_fixture=SINGLE_ENCODE_OUTPUT,
                ),
                # Test Case 2: Multiple sequences encode
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=multiple_seqs_request,
                    input_filename_template=MULTIPLE_SEQS_INPUT,
                    expected_output_fixture=MULTIPLE_ENCODE_OUTPUT,
                ),
                # Test Case 3: Masked sequence predict
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=masked_request,
                    input_filename_template=MASKED_INPUT,
                    expected_output_fixture=MASKED_PREDICT_OUTPUT,
                ),
            ],
        )
    ],
)


def generate() -> None:
    """Configures and runs the fixture generator for ESM-1b."""
    generator = FixtureGenerator(fixture_generation_suite)
    generator.generate()


if __name__ == "__main__":
    generate()

# Run with: python models/esm1b/fixture.py
