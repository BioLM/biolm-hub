from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.sadie.config import MODEL_FAMILY
from models.sadie.schema import (
    SADIEPredictRequest,
    SADIEPredictRequestItem,
    SADIEPredictRequestParams,
)

# Test input/output filenames (self-contained — see generate() below).
# Note: SADIE uses fixed filenames, not templates (single variant model).
PREDICT_INPUT = "input.json"
PREDICT_OUTPUT = "expected_output.json"

# Canonical antibody heavy/light chain pair, taken from the README's own
# documented (known-valid) usage examples — reused here so the golden fixture
# needs no pre-existing R2 asset. SADIE takes one bare "sequence" per item
# (chain type is auto-detected by HMM alignment, not passed in), so a heavy
# chain and a light chain are each their own batch item.
HEAVY_CHAIN_SEQUENCE = (
    "QVQLVQSGAEVKKPGASVKVSCKASGYTFTSYGISWVRQAPGQGLEWMGWISAYNGNTNYAQKLQGRVTM"
    "TTDTSTSTAYMELRSLRSDDTAVYYCARDGYSSGYYGMDVWGQGTTVTVSS"
)
LIGHT_CHAIN_SEQUENCE = (
    "DIQMTQSPSSVSASVGDRVTITCRASQSIGSFLAWYQQKPGKAPKLLIYEASTLKPGVPSRFSGSGSGT"
    "DFTLTISSLQPEDFANYYCHQYAAYPWTFGGGTKVEIK"
)


def _build_fixture_generation_suite() -> TestSuite:
    """Build the fixture-generation suite (single SADIE variant).

    The input is inlined (self-contained), so importing this module never
    touches R2 — `generate()` writes the input to R2 alongside the generated
    output.
    """
    predict_request = SADIEPredictRequest(
        params=SADIEPredictRequestParams(
            scheme="chothia",
            region_assign="imgt",
            scfv=False,
            allowed_chain=["H", "K", "L"],
        ),
        items=[
            SADIEPredictRequestItem(sequence=HEAVY_CHAIN_SEQUENCE),
            SADIEPredictRequestItem(sequence=LIGHT_CHAIN_SEQUENCE),
        ],
    )

    return TestSuite(
        model_family=MODEL_FAMILY,
        r2_fixture_subdir="models",
        variant_test_mappings=[
            # Single mapping for the single variant
            VariantTestMapping(
                variant_config={},  # Empty dict for single variant
                test_cases=[
                    ActionTestCase(
                        action_name=ModelActions.PREDICT,
                        input_fixture=predict_request,
                        input_filename_template=PREDICT_INPUT,
                        expected_output_fixture=PREDICT_OUTPUT,
                        tolerances={"rel_tol": 1e-5},  # Tight tolerances for SADIE
                        request_schema=None,  # Send raw JSON - SADIE model uses Pydantic v1
                    ),
                ],
            )
        ],
    )


def generate():
    """Configures and runs the fixture generator for the SADIE single variant."""
    generator = FixtureGenerator(_build_fixture_generation_suite())
    generator.generate()


if __name__ == "__main__":
    generate()

# Run with: python models/sadie/fixture.py
