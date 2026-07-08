from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.dna_chisel.config import MODEL_FAMILY
from models.dna_chisel.schema import (
    DnaChiselEncodeRequest,
    DnaChiselEncodeRequestItem,
    DnaChiselEncodeRequestParams,
    DnaChiselFeatureOptions,
    SupportedSpecies,
)

EXPLICIT_INPUT = "encode_input_explicit.json"
DEFAULT_INPUT = "encode_input_default.json"
EXPLICIT_OUTPUT = "encode_expected_output_explicit.json"
DEFAULT_OUTPUT = "encode_expected_output_default.json"

# Create TestSuite for fixture generation with programmatic inputs
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single mapping for the single variant
        VariantTestMapping(
            variant_config={},  # Empty dict for single-variant model
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_filename_template=EXPLICIT_INPUT,
                    # Programmatic input with explicit parameters
                    input_fixture=DnaChiselEncodeRequest(
                        params=DnaChiselEncodeRequestParams(
                            include=[
                                DnaChiselFeatureOptions.GC_CONTENT,
                                DnaChiselFeatureOptions.SEQUENCE_LENGTH,
                                DnaChiselFeatureOptions.AT_SKEW,
                            ],
                            species=SupportedSpecies.E_COLI,
                            restriction_enzymes=["EcoRI"],
                        ),
                        items=[DnaChiselEncodeRequestItem(sequence="ATGCGTACG")],
                    ),
                    expected_output_fixture=EXPLICIT_OUTPUT,
                ),
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_filename_template=DEFAULT_INPUT,
                    # Programmatic input with default parameters
                    input_fixture=DnaChiselEncodeRequest(
                        items=[DnaChiselEncodeRequestItem(sequence="ATGCGTACG")]
                    ),
                    expected_output_fixture=DEFAULT_OUTPUT,
                ),
            ],
        )
    ],
)


def generate() -> None:
    """Configures and runs the fixture generator"""
    generator = FixtureGenerator(fixture_generation_suite)
    generator.generate()


if __name__ == "__main__":
    generate()
