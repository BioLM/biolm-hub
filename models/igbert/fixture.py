"""IgBERT golden-fixture generation.

Self-contained: all inputs are inlined below (reused verbatim from this
model's own log_prob test inputs / README usage examples -- already
known-valid IgBert antibody sequences), so importing this module never
touches R2 or the network. `generate()` writes each input to R2 itself
alongside the generated golden output; no pre-existing R2 asset is required.
"""

from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.igbert.config import MODEL_FAMILY
from models.igbert.schema import (
    IgBertEncodeRequest,
    IgBertEncodeRequestItem,
    IgBertGenerateRequest,
    IgBertGenerateRequestItem,
)

# Test input/output filenames -- imported by test.py. Kept stable; do not
# rename without updating test.py's imports.
PAIRED_ENCODE_INPUT = "paired_encode_input.json"
UNPAIRED_ENCODE_INPUT = "unpaired_encode_input.json"
PAIRED_GENERATE_INPUT = "paired_generate_input.json"
UNPAIRED_GENERATE_INPUT = "unpaired_generate_input.json"
PAIRED_ENCODE_OUTPUT = "paired_encode_expected_output.json"
UNPAIRED_ENCODE_OUTPUT = "unpaired_encode_expected_output.json"
PAIRED_GENERATE_OUTPUT = "paired_generate_expected_output.json"
UNPAIRED_GENERATE_OUTPUT = "unpaired_generate_expected_output.json"

# Canonical paired antibody sequences -- reused verbatim from this model's
# log_prob test inputs (`_create_paired_logprob_input`) in test.py, which are
# already exercised against the deployed model and known-valid IgBert inputs.
PAIRED_HEAVY_1 = "QVQLVQSGAEVKKPGASVKVSCKVSGYTSPTTIHWVRQAPGKGLEWMGGISPYRGDTIYAQKFQGRVTMTEDTSTDTAYMELSSLKSEDTAVYYCARDGYSSGYYGMDVWGQGTTVTVSS"
PAIRED_LIGHT_1 = "DIQMTQSPSSVSASVGDRVTITCRASQSIGSFLAWYQQKPGKAPKLLIYEASTLKPGVPSRFSGSGSGTDFTLTISSLQPEDFANYYCHQYAAYPWTFGGGTKVEIK"
PAIRED_HEAVY_2 = "QVQLVQSGAEVKKPGASVKVSCKVSGYPFTRSTIHWVRQAPGKGLEWMGGINAGTGDTIYAQKFQGRVTMTEDTSTDTAYMELSSLKSEDTAVYYCARDGYSSGYYGMDVWGQGTTVTVSS"
PAIRED_LIGHT_2 = "DIQMTQSPSSVSASVGDRVTITCRASQNIHSYLAWYQQKPGKAPKLLIYDASILASGVPSRFSGSGSGTDFTLTISSLQPEDFANYYCQQYSTHSWTFGGGTKVEIK"

# Canonical unpaired antibody sequences -- the two heavy chains above, used
# standalone via the `sequence` field (same pattern as
# `_create_unpaired_logprob_input` in test.py).
UNPAIRED_SEQ_1 = PAIRED_HEAVY_1
UNPAIRED_SEQ_2 = PAIRED_HEAVY_2

# Masked (generate) sequences -- taken verbatim from the README's documented
# "generate -- restore missing residues (paired)" usage example, a heavy/light
# pair already documented as a known-good masked input.
GENERATE_HEAVY = "QVQLVQSG*EVKKPGASVKVSCKVSGYTSPTTI*WVRQAPGKGLEWMG"
GENERATE_LIGHT = "DIQMTQSPSSVSASVGDRVTITCRASQ*IGSFLAWYQQKPGKAPKLLIY"
# Same base sequence as GENERATE_HEAVY (it equals the README's unpaired
# `encode` example prior to masking), used standalone for the unpaired
# variant's `sequence` field.
GENERATE_UNPAIRED_SEQ = GENERATE_HEAVY


def _build_fixture_generation_suite() -> TestSuite:
    """Build the fixture-generation suite (both paired and unpaired variants).

    Inputs are inlined (self-contained), so importing this module never
    touches R2, and `generate()` needs no manually-placed R2 inputs -- it
    writes these inputs to R2 alongside the generated outputs.
    """
    paired_encode_request = IgBertEncodeRequest(
        items=[
            IgBertEncodeRequestItem(
                heavy_chain=PAIRED_HEAVY_1, light_chain=PAIRED_LIGHT_1
            ),
            IgBertEncodeRequestItem(
                heavy_chain=PAIRED_HEAVY_2, light_chain=PAIRED_LIGHT_2
            ),
        ]
    )
    unpaired_encode_request = IgBertEncodeRequest(
        items=[
            IgBertEncodeRequestItem(sequence=UNPAIRED_SEQ_1),
            IgBertEncodeRequestItem(sequence=UNPAIRED_SEQ_2),
        ]
    )
    paired_generate_request = IgBertGenerateRequest(
        items=[
            IgBertGenerateRequestItem(
                heavy_chain=GENERATE_HEAVY, light_chain=GENERATE_LIGHT
            )
        ]
    )
    unpaired_generate_request = IgBertGenerateRequest(
        items=[IgBertGenerateRequestItem(sequence=GENERATE_UNPAIRED_SEQ)]
    )

    return TestSuite(
        model_family=MODEL_FAMILY,
        r2_fixture_subdir="models",
        variant_test_mappings=[
            # Paired model variant
            VariantTestMapping(
                variant_config={"MODEL_TYPE": "paired"},
                test_cases=[
                    ActionTestCase(
                        action_name=ModelActions.ENCODE,
                        input_fixture=paired_encode_request,
                        input_filename_template=PAIRED_ENCODE_INPUT,
                        expected_output_fixture=PAIRED_ENCODE_OUTPUT,
                        tolerances={"rel_tol": 1e-4},
                    ),
                    ActionTestCase(
                        action_name=ModelActions.GENERATE,
                        input_fixture=paired_generate_request,
                        input_filename_template=PAIRED_GENERATE_INPUT,
                        expected_output_fixture=PAIRED_GENERATE_OUTPUT,
                        tolerances={"rel_tol": 1e-4},
                    ),
                ],
            ),
            # Unpaired model variant
            VariantTestMapping(
                variant_config={"MODEL_TYPE": "unpaired"},
                test_cases=[
                    ActionTestCase(
                        action_name=ModelActions.ENCODE,
                        input_fixture=unpaired_encode_request,
                        input_filename_template=UNPAIRED_ENCODE_INPUT,
                        expected_output_fixture=UNPAIRED_ENCODE_OUTPUT,
                        tolerances={"rel_tol": 1e-4},
                    ),
                    ActionTestCase(
                        action_name=ModelActions.GENERATE,
                        input_fixture=unpaired_generate_request,
                        input_filename_template=UNPAIRED_GENERATE_INPUT,
                        expected_output_fixture=UNPAIRED_GENERATE_OUTPUT,
                        tolerances={"rel_tol": 1e-4},
                    ),
                ],
            ),
        ],
    )


def generate():
    """Configures and runs the fixture generator for both IgBert variants."""
    generator = FixtureGenerator(_build_fixture_generation_suite())
    generator.generate()


if __name__ == "__main__":
    generate()

# Run with: python models/igbert/fixture.py
