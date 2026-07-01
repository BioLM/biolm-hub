from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.commons.testing.shared_assets import STANDARD_PROTEIN
from models.esm2.config import MODEL_FAMILY, ESM2ModelSizes
from models.esm2.schema import ESM2EncodeRequest, ESM2PredictRequest

# Fixture input/output filenames. Inputs are self-contained (inlined below), so
# generation needs no pre-existing R2 assets — the generator writes these inputs
# to R2 alongside the generated outputs.
SINGLE_SEQ_INPUT = "single_seq_input.json"
MULTIPLE_SEQS_INPUT = "multiple_seqs_input.json"
MASKED_INPUT = "masked_input.json"
SINGLE_ENCODE_OUTPUT_TPL = "{variant.name}_single_encode_expected_output.json"
MULTIPLE_ENCODE_OUTPUT_TPL = "{variant.name}_multiple_encode_expected_output.json"
MASKED_PREDICT_OUTPUT_TPL = "{variant.name}_masked_predict_expected_output.json"

# A single <mask> at position 30 of the canonical protein, for masked prediction.
_MASKED_SEQUENCE = STANDARD_PROTEIN[:30] + "<mask>" + STANDARD_PROTEIN[31:]


def _build_fixture_generation_suite() -> TestSuite:
    """Build the fixture-generation suite (ESM2-3B variant only).

    Inputs are inlined (self-contained), so importing this module never touches
    R2 and `generate()` needs no manually-placed R2 inputs — it writes these
    inputs to R2 alongside the generated outputs.
    """
    single_seq_request = ESM2EncodeRequest.model_validate(
        {"items": [{"sequence": STANDARD_PROTEIN}]}
    )
    multiple_seqs_request = ESM2EncodeRequest.model_validate(
        {"items": [{"sequence": STANDARD_PROTEIN}, {"sequence": STANDARD_PROTEIN[:40]}]}
    )
    masked_request = ESM2PredictRequest.model_validate(
        {"items": [{"sequence": _MASKED_SEQUENCE}]}
    )

    return TestSuite(
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
    generator = FixtureGenerator(_build_fixture_generation_suite())
    # Test cases are now in the TestSuite, respecting variant filtering
    generator.generate()


if __name__ == "__main__":
    generate()

# Run with: python models/esm2/fixture.py
