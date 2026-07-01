from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.esmfold.config import MODEL_FAMILY
from models.esmfold.schema import ESMFoldPredictRequest, ESMFoldPredictRequestItem

# Fixture input/output filenames. Inputs are self-contained (inlined below), so
# generation needs no pre-existing R2 assets — the generator writes these inputs
# to R2 alongside the generated outputs.
MULTICHAIN_INPUT = "multichain_input.json"
SINGLECHAIN_INPUT = "singlechain_input.json"
MULTICHAIN_OUTPUT = "multichain_expected_output.json"
SINGLECHAIN_OUTPUT = "singlechain_expected_output.json"

# Canonical example sequences (also documented in README.md's Usage Examples).
# Single chain: a 65-residue protein used throughout the repo as a folding example.
_SINGLECHAIN_SEQUENCE = (
    "MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVLAGG"
)
# Multi-chain: two chains (separated by ":") derived from the same protein family,
# exercising ESMFold's multimer path.
_MULTICHAIN_SEQUENCE = "MKTVRQERLKSIVRILERSKEPVSGAQ:LAEELSVSRQVIVQDIAYLRSLGYN"


def _build_fixture_generation_suite() -> TestSuite:
    """Build the fixture-generation suite (ESMFold's single variant).

    Inputs are inlined (self-contained), so importing this module never touches
    R2 and `generate()` needs no manually-placed R2 inputs — it writes these
    inputs to R2 alongside the generated outputs.
    """
    singlechain_request = ESMFoldPredictRequest(
        items=[ESMFoldPredictRequestItem(sequence=_SINGLECHAIN_SEQUENCE)]
    )
    multichain_request = ESMFoldPredictRequest(
        items=[ESMFoldPredictRequestItem(sequence=_MULTICHAIN_SEQUENCE)]
    )

    return TestSuite(
        model_family=MODEL_FAMILY,
        r2_fixture_subdir="models",
        variant_test_mappings=[
            # Single mapping that applies to the only variant (no variants = empty config)
            VariantTestMapping(
                variant_config={},  # Applies to all (only) variants
                test_cases=[
                    ActionTestCase(
                        action_name=ModelActions.FOLD,
                        input_fixture=multichain_request,
                        input_filename_template=MULTICHAIN_INPUT,
                        expected_output_fixture=MULTICHAIN_OUTPUT,
                    ),
                    ActionTestCase(
                        action_name=ModelActions.FOLD,
                        input_fixture=singlechain_request,
                        input_filename_template=SINGLECHAIN_INPUT,
                        expected_output_fixture=SINGLECHAIN_OUTPUT,
                    ),
                ],
            )
        ],
    )


def generate():
    """Configures and runs the fixture generator for ESMFold's single variant."""
    generator = FixtureGenerator(_build_fixture_generation_suite())
    generator.generate()


if __name__ == "__main__":
    generate()

# Run with: python models/esmfold/fixture.py
