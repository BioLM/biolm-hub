from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.progen2.config import MODEL_FAMILY
from models.progen2.schema import (
    ProGen2GenerateParams,
    ProGen2GenerateRequest,
    ProGen2GenerateRequestItem,
)

# Fixture input filename. Self-contained (inlined below), so generation needs
# no pre-existing R2 assets — the generator writes this input to R2 itself.
# Kept as "input.json" because test.py imports this exact name/value and its
# custom validator (`_validate_progen2_generate`) re-reads this same file from
# R2 at test time to recompute the expected sample count / context / max
# length. It is variant-agnostic: test.py's VariantTestMapping uses an empty
# variant_config ({}), so the same input is replayed against all four ProGen2
# variants (oas/medium/large/bfd90).
GENERATE_INPUT = "input.json"

# Per-variant expected-output filename, written by the FixtureGenerator for
# reference/debugging only. test.py does NOT read this file — the generate()
# action is validated structurally via `_validate_progen2_generate` instead of
# a golden-output comparison — but a name is still required (and must vary per
# variant) so the four variants' outputs don't clobber a single shared path.
GENERATE_OUTPUT_TPL = "{variant.name}_generate_expected_output.json"

# Canonical seed context reused from README.md's documented usage example
# (Basic generation: extend a context sequence) — a short, unambiguous amino
# acid sequence known-valid for this model.
_CONTEXT = "MKTVRQERLKSIVRILERSKEPVSGAQ"


def _build_fixture_generation_suite() -> TestSuite:
    """Build the fixture-generation suite (applies to all ProGen2 variants).

    The input is inlined (self-contained), so importing this module never
    touches R2 and `generate()` needs no manually-placed R2 inputs — it writes
    this input to R2 alongside the (per-variant) generated outputs.
    """
    generate_request = ProGen2GenerateRequest(
        params=ProGen2GenerateParams(
            temperature=0.8,
            top_p=0.9,
            num_samples=1,  # Keep fixture generation small/fast
            max_length=48,  # A little past the 27-residue context, still short
            seed=42,  # Reproducible sampling for a stable fixture
        ),
        items=[ProGen2GenerateRequestItem(context=_CONTEXT)],
    )

    return TestSuite(
        model_family=MODEL_FAMILY,
        r2_fixture_subdir="models",
        variant_test_mappings=[
            VariantTestMapping(
                variant_config={},  # Empty dict means applies to ALL variants (matches test.py)
                test_cases=[
                    ActionTestCase(
                        action_name=ModelActions.GENERATE,
                        input_fixture=generate_request,
                        input_filename_template=GENERATE_INPUT,
                        expected_output_fixture=GENERATE_OUTPUT_TPL,
                    ),
                ],
            )
        ],
    )


def generate() -> None:
    """Configures and runs the fixture generator for ProGen2 (all variants)."""
    generator = FixtureGenerator(_build_fixture_generation_suite())
    generator.generate()


if __name__ == "__main__":
    # python models/progen2/fixture.py
    generate()
