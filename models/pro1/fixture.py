from models.commons.core.logging import get_logger
from models.commons.model.schema import ModelActions
from models.commons.testing.config import (
    ActionTestCase,
    TestSuite,
    VariantTestMapping,
)
from models.commons.testing.fixture import FixtureGenerator
from models.pro1.config import MODEL_FAMILY
from models.pro1.schema import (
    Pro1GenerateParams,
    Pro1GenerateRequest,
    Pro1KnownMutation,
    Pro1ProteinData,
    Pro1Reaction,
    Pro1Variant,
)

logger = get_logger(__name__)

# Test input/output filenames
INPUT1 = "input1.json"  # FGF-1 short fragment, default 8b variant
INPUT2 = "input2.json"  # With known mutations (iterative design)
INPUT3 = "input3.json"  # Minimal (sequence only)

# FGF-1 sequence (first 50 AA for fast fixture generation)
_FGF1_FRAGMENT = "MAEGEITTFTALTEKFNLPPGNYKKPKLLYCSNGGHFLRILPDGTV"

# Carbonic anhydrase II (first 40 AA)
_CA2_FRAGMENT = "MSHHWGYGKHNGPEHWHKDFPIAKGERQSPVDIDTH"

# Create TestSuite for fixture generation
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={"MODEL_VARIANT": Pro1Variant.SIZE_8B},
            test_cases=[],
        )
    ],
)


def generate():
    """Configure and run the fixture generator for Pro-1."""
    generator = FixtureGenerator(fixture_generation_suite)

    # Test Case 1: FGF-1 fragment with biological context.
    # max_new_tokens kept low (256) so CI integration tests fit in the 60-min
    # workflow budget — full inference quality is exercised by deployment tests.
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.GENERATE,
            input_fixture=Pro1GenerateRequest(
                params=Pro1GenerateParams(
                    max_iterations=1,
                    max_new_tokens=256,
                    seed=42,
                ),
                items=[
                    Pro1ProteinData(
                        sequence=_FGF1_FRAGMENT,
                        name="Fibroblast Growth Factor 1 (fragment)",
                        ec_number="",
                        reaction=[],
                        general_information=(
                            "FGF-1 is a therapeutic protein relevant for bone repair "
                            "and cancer. Wild-type Tm ~49C. K116E in the full-length "
                            "sequence improves Tm by +24C while maintaining FGFR-1 binding."
                        ),
                        known_mutations=[],
                    )
                ],
            ),
            input_filename_template=INPUT1,
            expected_output_fixture="pro1-generate-input1-expected_output.json",
        )
    )

    # Test Case 2: Iterative design with known mutation feedback
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.GENERATE,
            input_fixture=Pro1GenerateRequest(
                params=Pro1GenerateParams(
                    max_iterations=1,
                    max_new_tokens=256,
                    seed=42,
                ),
                items=[
                    Pro1ProteinData(
                        sequence=_CA2_FRAGMENT,
                        name="Human Carbonic Anhydrase II (fragment)",
                        ec_number="4.2.1.1",
                        reaction=[
                            Pro1Reaction(
                                substrates=["Carbon dioxide", "Water"],
                                products=["Bicarbonate", "H+"],
                            )
                        ],
                        general_information=(
                            "Industrial enzyme for carbon capture. "
                            "Stability at high temperatures is a key bottleneck."
                        ),
                        known_mutations=[
                            Pro1KnownMutation(
                                mutation="W5A",
                                effect="destabilizes by ~3C, avoid",
                            )
                        ],
                    )
                ],
            ),
            input_filename_template=INPUT2,
            expected_output_fixture="pro1-generate-input2-expected_output.json",
        )
    )

    # Test Case 3: Minimal input (sequence only)
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.GENERATE,
            input_fixture=Pro1GenerateRequest(
                params=Pro1GenerateParams(
                    max_iterations=1,
                    max_new_tokens=256,
                    seed=0,
                ),
                items=[
                    Pro1ProteinData(
                        sequence=_FGF1_FRAGMENT,
                    )
                ],
            ),
            input_filename_template=INPUT3,
            expected_output_fixture="pro1-generate-input3-expected_output.json",
        )
    )

    generator.generate()


if __name__ == "__main__":
    logger.info("Generating fixtures for Pro-1...")
    generate()
