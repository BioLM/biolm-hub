from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.omni_dna.config import MODEL_FAMILY
from models.omni_dna.schema import (
    OmniDNAEncodeIncludeOptions,
    OmniDNAEncodeRequest,
    OmniDNAEncodeRequestItem,
    OmniDNAEncodeRequestParams,
    OmniDNALogProbRequest,
    OmniDNALogProbRequestItem,
    OmniDNAModelSizes,
)

# Test input/output filenames. Inputs are self-contained (inlined below), so
# generation needs no pre-existing R2 assets — the generator writes these
# inputs to R2 alongside the generated outputs.
ENCODE_INPUT = "encode_input.json"
LOGPROB_INPUT = "logprob_input.json"

# Note: only 1b variant has test files
ENCODE_OUTPUT_TPL = "{variant.name}_encode_expected_output.json"
LOGPROB_OUTPUT_TPL = "{variant.name}_logprob_expected_output.json"

# Canonical DNA sequences (A/C/G/T only) — reused from README usage examples.
ENCODE_SEQUENCE = "ACGTACGTACGTACGT"
LOGPROB_SEQUENCE = "ATGATGATGATGATG"


def _build_fixture_generation_suite() -> TestSuite:
    """Build the fixture-generation suite (Omni-DNA 1B variant only).

    Inputs are inlined (self-contained), so importing this module never
    touches R2 and `generate()` needs no manually-placed R2 inputs — it writes
    these inputs to R2 alongside the generated outputs.
    """
    encode_request = OmniDNAEncodeRequest(
        params=OmniDNAEncodeRequestParams(
            include=[
                OmniDNAEncodeIncludeOptions.MEAN,
                OmniDNAEncodeIncludeOptions.LAST,
            ],
        ),
        items=[OmniDNAEncodeRequestItem(sequence=ENCODE_SEQUENCE)],
    )
    logprob_request = OmniDNALogProbRequest(
        items=[OmniDNALogProbRequestItem(sequence=LOGPROB_SEQUENCE)],
    )

    return TestSuite(
        model_family=MODEL_FAMILY,
        r2_fixture_subdir="models",
        variant_test_mappings=[
            # Only the 1b variant has test files
            VariantTestMapping(
                variant_config={"MODEL_SIZE": OmniDNAModelSizes.SIZE_1B},
                test_cases=[
                    ActionTestCase(
                        action_name=ModelActions.ENCODE,
                        input_fixture=encode_request,
                        input_filename_template=ENCODE_INPUT,
                        # Template: will be formatted with variant.name (e.g., "1b_encode_expected_output.json")
                        expected_output_fixture=ENCODE_OUTPUT_TPL,
                        tolerances={"rel_tol": 1e-4},
                    ),
                    ActionTestCase(
                        action_name=ModelActions.LOG_PROB,
                        input_fixture=logprob_request,
                        input_filename_template=LOGPROB_INPUT,
                        # Template: will be formatted with variant.name (e.g., "1b_logprob_expected_output.json")
                        expected_output_fixture=LOGPROB_OUTPUT_TPL,
                        tolerances={"rel_tol": 1e-4},
                    ),
                ],
            )
        ],
    )


def generate() -> None:
    """Configures and runs the fixture generator for the Omni-DNA 1B variant."""
    generator = FixtureGenerator(_build_fixture_generation_suite())
    generator.generate()


if __name__ == "__main__":
    generate()

# Run with: python models/omni_dna/fixture.py
