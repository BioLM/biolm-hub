from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.immunebuilder.config import MODEL_FAMILY
from models.immunebuilder.schema import (
    ImmuneBuilderFoldRequest,
    ImmuneBuilderModelTypes,
)

# Test input/output filenames. Inputs are self-contained (inlined below), so
# generation needs no pre-existing R2 assets — the generator writes these
# inputs to R2 alongside the generated outputs. `{variant.name}` resolves to
# each of "abodybuilder2" / "nanobodybuilder2" / "tcrbuilder2" /
# "tcrbuilder2plus" for the single MODEL_TYPE variant axis.
PREDICT_INPUT_TPL = "{variant.name}_predict_input.json"
PREDICT_OUTPUT_TPL = "{variant.name}_predict_expected_output.json"

# Canonical antibody heavy/light pair (paired VH/VL), reused from README.md's
# ABodyBuilder2 usage example — known-valid input for this model.
ABODY_HEAVY_CHAIN = (
    "EVQLVESGGGLVQPGGSLRLSCAASGFTFSDYAMSWVRQAPGKGLEWVSGISGSGGSTYYADSVKGRFTIS"
    "RDNSKNTLYLQMNSLRAEDTAVYYCAKDRLSITIRPRYYGLDVWGQGTTVTVSS"
)
ABODY_LIGHT_CHAIN = (
    "DIQMTQSPSSLSASVGDRVTITCRASQSISSYLNWYQQKPGKAPKLLIYAASSLQSGVPSRFSGSGSGTDF"
    "TLTISSLQPEDFATYYCQQSYSTPLTFGGGTKVEIK"
)

# Canonical nanobody (VHH, heavy-chain only) sequence, reused from
# README.md's NanoBodyBuilder2 usage example.
NANOBODY_HEAVY_CHAIN = (
    "QVQLQESGGGLVQPGGSLRLSCAASGRTFSSYAMGWFRQAPGKEREFVAAISWSGGSTYYADSVKGRFTIS"
    "RDNAKNTVYLQMNSLKPEDTAVYYCAADSTIYASYYECGHGLSTGGYGYDSWGQGTQVTVSS"
)

# Canonical alpha/beta TCR pair, reused from README.md's TCRBuilder2 usage
# example. Shared by both the tcrbuilder2 and tcrbuilder2plus variants.
TCR_ALPHA_CHAIN = (
    "AQEVTQIPAALSVPEGENLVLNCSFTDSAIYNLQWFRQDPGKGLTSLLLIQSSQREQTSGRLNASLDKSSG"
    "RSTLYIAASQPGDSATYLCAVRPTSGGSYIPTFGRGTSLIVHPY"
)
TCR_BETA_CHAIN = (
    "DAGVTQTPRNHVTISEGDKITVRCEKSTVSNFLYELFWYRQDPGLGLRLIYFSYDVKMKEKGDIPDGYSVS"
    "RNKKPNFYEALISKLNVSDSALYFCASSQETQYFGPGTRLTVL"
)


def _build_fixture_generation_suite() -> TestSuite:
    """Build the fixture-generation suite (all four ImmuneBuilder variants).

    Inputs are inlined (self-contained), so importing this module never
    touches R2 and `generate()` needs no manually-placed R2 inputs — it
    writes these inputs to R2 alongside the generated outputs. Each variant
    requires a different chain combination (paired H+L, H-only, or A+B), so
    each gets its own variant-scoped mapping with the matching request.
    """
    abody_request = ImmuneBuilderFoldRequest.model_validate(
        {
            "items": [
                {
                    "heavy_chain": ABODY_HEAVY_CHAIN,
                    "light_chain": ABODY_LIGHT_CHAIN,
                }
            ]
        }
    )
    nanobody_request = ImmuneBuilderFoldRequest.model_validate(
        {"items": [{"heavy_chain": NANOBODY_HEAVY_CHAIN}]}
    )
    tcr_request = ImmuneBuilderFoldRequest.model_validate(
        {
            "items": [
                {
                    "tcr_alpha": TCR_ALPHA_CHAIN,
                    "tcr_beta": TCR_BETA_CHAIN,
                }
            ]
        }
    )

    return TestSuite(
        model_family=MODEL_FAMILY,
        r2_fixture_subdir="models",
        variant_test_mappings=[
            VariantTestMapping(
                variant_config={"MODEL_TYPE": ImmuneBuilderModelTypes.ABODYBUILDER2},
                test_cases=[
                    ActionTestCase(
                        action_name=ModelActions.FOLD,
                        input_fixture=abody_request,
                        input_filename_template=PREDICT_INPUT_TPL,
                        expected_output_fixture=PREDICT_OUTPUT_TPL,
                    ),
                ],
            ),
            VariantTestMapping(
                variant_config={"MODEL_TYPE": ImmuneBuilderModelTypes.NANOBODYBUILDER2},
                test_cases=[
                    ActionTestCase(
                        action_name=ModelActions.FOLD,
                        input_fixture=nanobody_request,
                        input_filename_template=PREDICT_INPUT_TPL,
                        expected_output_fixture=PREDICT_OUTPUT_TPL,
                    ),
                ],
            ),
            VariantTestMapping(
                variant_config={"MODEL_TYPE": ImmuneBuilderModelTypes.TCRBUILDER2},
                test_cases=[
                    ActionTestCase(
                        action_name=ModelActions.FOLD,
                        input_fixture=tcr_request,
                        input_filename_template=PREDICT_INPUT_TPL,
                        expected_output_fixture=PREDICT_OUTPUT_TPL,
                    ),
                ],
            ),
            VariantTestMapping(
                variant_config={"MODEL_TYPE": ImmuneBuilderModelTypes.TCRBUILDER2PLUS},
                test_cases=[
                    ActionTestCase(
                        action_name=ModelActions.FOLD,
                        input_fixture=tcr_request,
                        input_filename_template=PREDICT_INPUT_TPL,
                        expected_output_fixture=PREDICT_OUTPUT_TPL,
                    ),
                ],
            ),
        ],
    )


def generate() -> None:
    """Configures and runs the fixture generator for all ImmuneBuilder variants."""
    generator = FixtureGenerator(_build_fixture_generation_suite())
    generator.generate()


if __name__ == "__main__":
    generate()

# Run with: python models/immunebuilder/fixture.py
