from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.commons.testing.shared_assets import STANDARD_PROTEIN
from models.esm1v.config import MODEL_FAMILY
from models.esm1v.schema import ESM1vPredictRequest, ESM1vPredictRequestItem

# Test input/output filenames. The input is self-contained (inlined below), so
# generation needs no pre-existing R2 assets — the generator writes this input
# to R2 alongside the generated per-variant outputs.
PREDICT_INPUT = "predict_input.json"
PREDICT_OUTPUT_TPL = "{variant.name}_predict_expected_output.json"

# A single <mask> at position 30 of the canonical protein (replacing, not
# inserting, so length and single-occurrence constraints stay satisfied), for
# zero-shot masked-position prediction.
_MASKED_SEQUENCE = STANDARD_PROTEIN[:30] + "<mask>" + STANDARD_PROTEIN[31:]


def _build_fixture_generation_suite() -> TestSuite:
    """Build the fixture-generation suite (applies to ALL variants: n1-n5, all).

    The input is inlined (self-contained), so importing this module never
    touches R2 and `generate()` needs no manually-placed R2 inputs. The same
    input is written to R2 once and reused; a per-variant expected-output
    fixture is then generated for each of the 6 ESM1v variants (n1-n5, all).
    """
    predict_request = ESM1vPredictRequest(
        items=[ESM1vPredictRequestItem(sequence=_MASKED_SEQUENCE)]
    )

    return TestSuite(
        model_family=MODEL_FAMILY,
        r2_fixture_subdir="models",
        variant_test_mappings=[
            # Single mapping that applies to ALL variants — same input, one
            # expected-output fixture generated per variant (n1-n5, all).
            VariantTestMapping(
                variant_config={},
                test_cases=[
                    ActionTestCase(
                        action_name=ModelActions.PREDICT,
                        input_fixture=predict_request,
                        input_filename_template=PREDICT_INPUT,
                        expected_output_fixture=PREDICT_OUTPUT_TPL,
                    ),
                ],
            )
        ],
    )


def generate():
    """Configures and runs the fixture generator for all ESM1v variants."""
    generator = FixtureGenerator(_build_fixture_generation_suite())
    generator.generate()


if __name__ == "__main__":
    generate()

# Run with: python models/esm1v/fixture.py
