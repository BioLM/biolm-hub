"""IgT5 test fixtures.

Inputs are self-contained (inlined below), so fixture generation needs no
pre-existing R2 assets — the generator writes these inputs to R2 alongside the
generated outputs. The canonical heavy/light pair is the one already
documented in README.md's "Usage Examples" section (known-valid for this
model).
"""

from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.igt5.config import MODEL_FAMILY
from models.igt5.schema import (
    IgT5EncodeRequest,
    IgT5EncodeRequestItem,
    IgT5EncodeRequestParams,
)

# Test input/output filenames. Templated on {variant.name} ("paired" /
# "unpaired") so each variant gets its own input + output fixture files.
ENCODE_INPUT_TPL = "{variant.name}_encode_input.json"
ENCODE_OUTPUT_TPL = "{variant.name}_encode_expected_output.json"

# Canonical antibody heavy/light pair — reused from README.md's Usage Examples
# (known-valid for this model, keeps fixtures and docs from drifting apart).
HEAVY_CHAIN = "QVQLVQSGAEVKKPGASVKVSCKVSGYTSPTTIHWVRQAPGKGLEWMG"
LIGHT_CHAIN = "DIQMTQSPSSVSASVGDRVTITCRASQSIGSFLAWYQQKPGKAPKLLIY"


def _build_fixture_generation_suite() -> TestSuite:
    """Build the fixture-generation suite (paired + unpaired variants).

    Inputs are inlined (self-contained), so importing this module never
    touches R2 and `generate()` needs no manually-placed R2 inputs — it writes
    these inputs to R2 alongside the generated outputs.
    """
    paired_request = IgT5EncodeRequest(
        params=IgT5EncodeRequestParams(include=["mean", "residue"]),
        items=[IgT5EncodeRequestItem(heavy_chain=HEAVY_CHAIN, light_chain=LIGHT_CHAIN)],
    )
    unpaired_request = IgT5EncodeRequest(
        params=IgT5EncodeRequestParams(include=["mean", "residue"]),
        items=[IgT5EncodeRequestItem(sequence=HEAVY_CHAIN)],
    )

    return TestSuite(
        model_family=MODEL_FAMILY,
        r2_fixture_subdir="models",
        variant_test_mappings=[
            # Paired variant: heavy_chain + light_chain input.
            VariantTestMapping(
                variant_config={"MODEL_TYPE": "paired"},
                test_cases=[
                    ActionTestCase(
                        action_name=ModelActions.ENCODE,
                        input_fixture=paired_request,
                        input_filename_template=ENCODE_INPUT_TPL,
                        expected_output_fixture=ENCODE_OUTPUT_TPL,
                        tolerances={"rel_tol": 1e-4},
                    ),
                ],
            ),
            # Unpaired variant: single-chain `sequence` input.
            VariantTestMapping(
                variant_config={"MODEL_TYPE": "unpaired"},
                test_cases=[
                    ActionTestCase(
                        action_name=ModelActions.ENCODE,
                        input_fixture=unpaired_request,
                        input_filename_template=ENCODE_INPUT_TPL,
                        expected_output_fixture=ENCODE_OUTPUT_TPL,
                        tolerances={"rel_tol": 1e-4},
                    ),
                ],
            ),
        ],
    )


def generate():
    """Configures and runs the fixture generator for both IgT5 variants."""
    generator = FixtureGenerator(_build_fixture_generation_suite())
    # Test cases are in the TestSuite, respecting variant filtering.
    generator.generate()


if __name__ == "__main__":
    generate()

# Run with: python models/igt5/fixture.py
