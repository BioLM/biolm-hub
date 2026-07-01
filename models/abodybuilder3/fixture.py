from models.abodybuilder3.config import MODEL_FAMILY
from models.abodybuilder3.schema import (
    AbodyBuilder3PredictRequest,
    AbodyBuilder3PredictRequestItem,
    AbodyBuilder3PredictRequestParams,
)
from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator

# Test input/output filenames. Inputs are self-contained (inlined below), so
# generation needs no pre-existing R2 assets — the generator writes these
# inputs to R2 alongside the generated outputs.
PREDICT_INPUT = "predict_input.json"
PREDICT_OUTPUT_TPL = "{variant.name}_predict_expected_output.json"

# Canonical paired heavy/light chain sequences, reused from the README's
# "Predict antibody structure" usage example (known-valid for this model).
HEAVY_CHAIN = (
    "EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISGSGGSTYYADSVKGRFTIS"
    "RDNSKNTLYLQMNSLRAEDTAVYYCAR"
)
LIGHT_CHAIN = (
    "DIQMTQSPSSLSASVGDRVTITCRASQSISSYLNWYQQKPGKAPKLLIYAASSLQSGVPSRFSGSGSGTD"
    "FTLTISSLQPEDFATYYCQQSYSTPLT"
)


def _build_fixture_generation_suite() -> TestSuite:
    """Build the fixture-generation suite (applies to all variants).

    The input is inlined (self-contained), so importing this module never
    touches R2 or the network — `generate()` writes the input to R2 alongside
    the generated outputs for each resolved variant (language, plddt).
    """
    predict_request = AbodyBuilder3PredictRequest(
        params=AbodyBuilder3PredictRequestParams(plddt=False, seed=42),
        items=[
            AbodyBuilder3PredictRequestItem(
                heavy_chain=HEAVY_CHAIN,
                light_chain=LIGHT_CHAIN,
            )
        ],
    )

    return TestSuite(
        model_family=MODEL_FAMILY,
        r2_fixture_subdir="models",
        variant_test_mappings=[
            VariantTestMapping(
                variant_config={},  # Applies to all variants (language, plddt)
                test_cases=[
                    # Test Case 1: fold() on a canonical heavy/light chain pair
                    ActionTestCase(
                        action_name=ModelActions.FOLD,
                        input_fixture=predict_request,
                        input_filename_template=PREDICT_INPUT,
                        expected_output_fixture=PREDICT_OUTPUT_TPL,
                        tolerances={
                            "rel_tol": 1e-3,
                            "cosine_distance_threshold": 0.02,
                            "pdb_rmsd_threshold": 0.05,
                        },
                    ),
                ],
            )
        ],
    )


def generate() -> None:
    """Configures and runs the fixture generator for all AbodyBuilder3 variants"""
    generator = FixtureGenerator(_build_fixture_generation_suite())
    generator.generate()


if __name__ == "__main__":
    generate()

# Run with: python models/abodybuilder3/fixture.py
