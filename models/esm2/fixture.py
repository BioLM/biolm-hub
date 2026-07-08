from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.commons.testing.shared_assets import STANDARD_PROTEIN
from models.esm2.config import MODEL_FAMILY
from models.esm2.schema import ESM2EncodeRequest, ESM2ModelSizes, ESM2PredictRequest

# Fixture input/output filenames. Inputs are self-contained (inlined below), so
# generation needs no pre-existing R2 assets — the generator writes these inputs
# to R2 alongside the generated outputs. The input filenames are variant-agnostic
# (no {variant} template), so they are written once and shared across every size;
# only the output filenames are per-variant via the {variant.name} template.
SINGLE_SEQ_INPUT = "single_seq_input.json"
MULTIPLE_SEQS_INPUT = "multiple_seqs_input.json"
MASKED_INPUT = "masked_input.json"
SINGLE_ENCODE_OUTPUT_TPL = "{variant.name}_single_encode_expected_output.json"
MULTIPLE_ENCODE_OUTPUT_TPL = "{variant.name}_multiple_encode_expected_output.json"
MASKED_PREDICT_OUTPUT_TPL = "{variant.name}_masked_predict_expected_output.json"

# Variants that get an encode/predict golden. Each size has its own golden because
# embeddings/logits are size-specific; test.py golden-tests exactly these sizes.
# The remaining sizes (8m, 650m) are covered by the validator-based log_prob case
# (all variants) plus the deployment tests, so no golden is generated for them.
GOLDEN_SIZES = [
    ESM2ModelSizes.SIZE_35M,
    ESM2ModelSizes.SIZE_150M,
    ESM2ModelSizes.SIZE_3B,
]

# A single <mask> at position 30 of the canonical protein, for masked prediction.
_MASKED_SEQUENCE = STANDARD_PROTEIN[:30] + "<mask>" + STANDARD_PROTEIN[31:]


def _build_test_cases() -> list[ActionTestCase]:
    """Build the 3 golden test cases (single encode, multiple encode, masked predict).

    Inputs are inlined (self-contained), so importing this module never touches R2
    and `generate()` needs no manually-placed R2 inputs — it writes these inputs to
    R2 alongside the generated outputs.
    """
    single_seq_request = ESM2EncodeRequest.model_validate(
        {"items": [{"sequence": STANDARD_PROTEIN}]}
    )
    multiple_seqs_request = ESM2EncodeRequest.model_validate(
        {"items": [{"sequence": STANDARD_PROTEIN}, {"sequence": STANDARD_PROTEIN[:40]}]}
    )
    masked_request = ESM2PredictRequest.model_validate(
        {"items": [{"sequence": _MASKED_SEQUENCE}]}
    )

    return [
        # Test Case 1: Single sequence encode
        ActionTestCase(
            action_name=ModelActions.ENCODE,
            input_fixture=single_seq_request,
            input_filename_template=SINGLE_SEQ_INPUT,
            expected_output_fixture=SINGLE_ENCODE_OUTPUT_TPL,
        ),
        # Test Case 2: Multiple sequences encode
        ActionTestCase(
            action_name=ModelActions.ENCODE,
            input_fixture=multiple_seqs_request,
            input_filename_template=MULTIPLE_SEQS_INPUT,
            expected_output_fixture=MULTIPLE_ENCODE_OUTPUT_TPL,
        ),
        # Test Case 3: Masked sequence predict
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=masked_request,
            input_filename_template=MASKED_INPUT,
            expected_output_fixture=MASKED_PREDICT_OUTPUT_TPL,
        ),
    ]


def _build_fixture_generation_suite(sizes: list[ESM2ModelSizes]) -> TestSuite:
    """Build the fixture-generation suite for the given ESM2 sizes.

    One VariantTestMapping per requested size; variants outside ``sizes`` match no
    mapping and are skipped by the generator. The variant-agnostic input files are
    written once (deduped by the generator), and each size gets its own per-variant
    golden output via the {variant.name} template.
    """
    return TestSuite(
        model_family=MODEL_FAMILY,
        r2_fixture_subdir="models",
        variant_test_mappings=[
            VariantTestMapping(
                variant_config={"MODEL_SIZE": size},
                test_cases=_build_test_cases(),
            )
            for size in sizes
        ],
    )


def generate(sizes: list[ESM2ModelSizes] | None = None) -> None:
    """Configure and run the fixture generator for the requested ESM2 sizes.

    Args:
        sizes: ESM2 sizes to generate goldens for. Defaults to GOLDEN_SIZES
            (35m, 150m, 3b). Pass a subset (e.g. [SIZE_35M, SIZE_150M]) to skip
            the heavy 3B cold-start when its golden already exists.
    """
    generator = FixtureGenerator(_build_fixture_generation_suite(sizes or GOLDEN_SIZES))
    # Test cases live in the TestSuite, so variant filtering is respected.
    generator.generate()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate ESM2 golden fixtures.")
    parser.add_argument(
        "--sizes",
        nargs="+",
        choices=[s.value for s in GOLDEN_SIZES],
        default=None,
        help=(
            "ESM2 sizes to generate (space-separated). "
            "Defaults to all golden sizes: 35m 150m 3b."
        ),
    )
    args = parser.parse_args()
    selected = (
        [ESM2ModelSizes(v) for v in args.sizes] if args.sizes is not None else None
    )
    generate(sizes=selected)

# Run with: python models/esm2/fixture.py                 # all golden sizes
#           python models/esm2/fixture.py --sizes 35m 150m # only the new sizes
