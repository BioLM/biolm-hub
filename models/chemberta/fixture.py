from models.chemberta.config import MODEL_FAMILY
from models.chemberta.schema import ChemBERTaEncodeRequest, ChemBERTaLogProbRequest
from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator

# Golden fixture filenames for the two actions.
#
# Inputs are inlined below (self-contained), so importing this module never
# touches R2 and `generate()` needs no pre-existing R2 assets — the generator
# writes these inputs to R2 and then writes the model's output next to them.
# `pytest --collect-only` therefore works with no Modal/R2 credentials.
#
# Single-variant model: these are plain filenames (no `{variant.name}`).
ENCODE_INPUT = "encode_input.json"
ENCODE_OUTPUT = "encode_expected_output.json"
LOGPROB_INPUT = "logprob_input.json"
LOGPROB_OUTPUT = "logprob_expected_output.json"

# Canonical, well-known small-molecule SMILES used as golden inputs:
#   aspirin, caffeine, ethanol.
_ASPIRIN = "CC(=O)Oc1ccccc1C(=O)O"
_CAFFEINE = "Cn1cnc2c1c(=O)n(C)c(=O)n2C"
_ETHANOL = "CCO"


def _build_fixture_generation_suite() -> TestSuite:
    encode_request = ChemBERTaEncodeRequest.model_validate(
        {"items": [{"smiles": _ASPIRIN}, {"smiles": _CAFFEINE}]}
    )
    logprob_request = ChemBERTaLogProbRequest.model_validate(
        {"items": [{"smiles": _ASPIRIN}, {"smiles": _ETHANOL}]}
    )

    return TestSuite(
        model_family=MODEL_FAMILY,
        r2_fixture_subdir="models",
        variant_test_mappings=[
            VariantTestMapping(
                variant_config={},  # {} = the single chemberta variant
                test_cases=[
                    ActionTestCase(
                        action_name=ModelActions.ENCODE,
                        input_fixture=encode_request,
                        input_filename_template=ENCODE_INPUT,
                        expected_output_fixture=ENCODE_OUTPUT,
                    ),
                    ActionTestCase(
                        action_name=ModelActions.LOG_PROB,
                        input_fixture=logprob_request,
                        input_filename_template=LOGPROB_INPUT,
                        expected_output_fixture=LOGPROB_OUTPUT,
                    ),
                ],
            )
        ],
    )


def generate() -> None:
    """Configure and run the fixture generator for the ChemBERTa model."""
    generator = FixtureGenerator(_build_fixture_generation_suite())
    generator.generate()


if __name__ == "__main__":
    generate()

# Run with: python models/chemberta/fixture.py
