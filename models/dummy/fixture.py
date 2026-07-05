from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.dummy.config import MODEL_FAMILY
from models.dummy.schema import DummySvcRequest

# Golden fixture filenames for the single `predict` action.
#
# The input is inlined below (self-contained), so importing this module never
# touches R2 and `generate()` needs no pre-existing R2 assets — the generator
# writes this input to R2 and then writes the model's output next to it. Keep
# fixture inputs self-contained this way (inline a canonical value, or import
# one from `models.commons.testing.shared_assets`); do NOT read from R2 at
# module scope, so `pytest --collect-only` works with no Modal/R2 credentials.
#
# Single-variant model: these paths are plain filenames. Only multi-variant
# models template the variant into the path (e.g. "{variant.name}_output.json").
PREDICT_INPUT = "predict_input.json"
PREDICT_OUTPUT = "predict_expected_output.json"


def _build_fixture_generation_suite() -> TestSuite:
    """Build the fixture-generation suite for the dummy model.

    Mirrors the structure of `test.py` (same `MODEL_FAMILY`, same `predict`
    action, same request schema) but declares `input_filename_template` +
    `expected_output_fixture` so the generator writes golden input/output JSON
    to `test-data/models/dummy/` in R2. `test.py` itself validates the dummy
    output with a custom validator; most models instead compare against the
    golden output written here.
    """
    predict_request = DummySvcRequest.model_validate(
        {"items": [{"dummy_model_input_field": "test_input"}]}
    )

    return TestSuite(
        model_family=MODEL_FAMILY,
        r2_fixture_subdir="models",
        variant_test_mappings=[
            VariantTestMapping(
                variant_config={},  # {} = the single dummy variant
                test_cases=[
                    ActionTestCase(
                        action_name=ModelActions.PREDICT,
                        input_fixture=predict_request,
                        input_filename_template=PREDICT_INPUT,
                        expected_output_fixture=PREDICT_OUTPUT,
                    ),
                ],
            )
        ],
    )


def generate() -> None:
    """Configure and run the fixture generator for the dummy model."""
    generator = FixtureGenerator(_build_fixture_generation_suite())
    # Test cases live in the TestSuite, so variant filtering is respected.
    generator.generate()


if __name__ == "__main__":
    generate()

# Run with: python models/dummy/fixture.py
