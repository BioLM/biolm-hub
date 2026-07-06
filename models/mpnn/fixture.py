from pathlib import Path

from models.commons.core.logging import get_logger
from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.mpnn.config import MODEL_FAMILY
from models.mpnn.schema import (
    AllMPNNGenerateParams,
    MPNNGenerateRequest,
    MPNNGenerateRequestItem,
)

logger = get_logger(__name__)

# Test input/output filenames. Inputs are self-contained (read from a local
# fixture file below), so generation needs no pre-existing R2 assets — the
# generator writes these inputs to R2 itself, alongside the generated outputs.
#
# MPNN's wire schema (MPNNGenerateRequest / AllMPNNGenerateParams) is the same
# for every MODEL_TYPE — the app re-validates/filters params per-variant
# server-side (see mpnn_schema_map in models/mpnn/app.py) — so these 4
# variant-agnostic inputs are valid for ALL variants (including hyper), and
# test.py's 3-variant smoke test can reuse INPUT1 unmodified.
INPUT1 = "input1.json"
INPUT2 = "input2.json"
INPUT3 = "input3.json"
INPUT4 = "input4.json"

# 1CRN (Crambin, a small 46-residue single-chain protein) committed locally as
# byte-identical to `https://files.rcsb.org/download/1CRN.pdb` so golden
# generation is self-contained and doesn't depend on RCSB being reachable.
_TEST_DATA_DIR = Path(__file__).parent / "test_data"
_1CRN_PDB_PATH = _TEST_DATA_DIR / "1CRN.pdb"


def _load_pdb(path: Path) -> str:
    """Read a local PDB-format structure file and return it as text."""
    return path.read_text(encoding="utf-8")


# TestSuite skeleton — test cases are built lazily inside generate() to keep
# file I/O out of module scope / plain imports of this module (test.py
# imports INPUT1 above at import time).
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single mapping that applies to ALL variants (including hyper)
        VariantTestMapping(
            variant_config={},  # Empty dict means applies to ALL variants
            test_cases=[],  # populated by _build_test_cases() inside generate()
        )
    ],
)


def _build_test_cases() -> list[ActionTestCase]:
    """
    Loads a canonical small structure from a local fixture file and builds the
    4 GENERATE test cases (same backbone, 4 different parameter settings)
    shared across all MPNN variants.
    """
    logger.info("Loading local PDB structure...")
    # 1CRN: Crambin, a small (46-residue) single-chain protein — a fast, cheap
    # canonical backbone for inverse folding (chain "A", residues 1-46).
    pdb_1crn = _load_pdb(_1CRN_PDB_PATH)
    logger.info("PDB structure loaded successfully")

    return [
        # Baseline design: near-greedy sampling, small batch.
        ActionTestCase(
            action_name=ModelActions.GENERATE,
            input_fixture=MPNNGenerateRequest(
                params=AllMPNNGenerateParams(
                    seed=42,
                    temperature=0.1,
                    batch_size=2,
                    number_of_batches=1,
                ),
                items=[MPNNGenerateRequestItem(pdb=pdb_1crn)],
            ),
            input_filename_template=INPUT1,
            expected_output_fixture="{variant.modal_app_name}-generate-input1-expected_output.json",
        ),
        # Higher-temperature sampling for more diverse designs.
        ActionTestCase(
            action_name=ModelActions.GENERATE,
            input_fixture=MPNNGenerateRequest(
                params=AllMPNNGenerateParams(
                    seed=7,
                    temperature=0.3,
                    batch_size=4,
                    number_of_batches=1,
                ),
                items=[MPNNGenerateRequestItem(pdb=pdb_1crn)],
            ),
            input_filename_template=INPUT2,
            expected_output_fixture="{variant.modal_app_name}-generate-input2-expected_output.json",
        ),
        # Constrained design: fix the first 3 residues of chain A, redesign the rest.
        ActionTestCase(
            action_name=ModelActions.GENERATE,
            input_fixture=MPNNGenerateRequest(
                params=AllMPNNGenerateParams(
                    seed=123,
                    temperature=0.1,
                    batch_size=2,
                    number_of_batches=1,
                    fixed_residues=["A1", "A2", "A3"],
                    chains_to_design=["A"],
                ),
                items=[MPNNGenerateRequestItem(pdb=pdb_1crn)],
            ),
            input_filename_template=INPUT3,
            expected_output_fixture="{variant.modal_app_name}-generate-input3-expected_output.json",
        ),
        # Side-chain packing enabled - exercises the all-atom packed-output path.
        ActionTestCase(
            action_name=ModelActions.GENERATE,
            input_fixture=MPNNGenerateRequest(
                params=AllMPNNGenerateParams(
                    seed=99,
                    temperature=0.1,
                    batch_size=1,
                    number_of_batches=1,
                    pack_side_chains=True,
                    number_of_packs_per_design=1,
                    sc_num_samples=4,
                    sc_num_denoising_steps=2,
                ),
                items=[MPNNGenerateRequestItem(pdb=pdb_1crn)],
            ),
            input_filename_template=INPUT4,
            expected_output_fixture="{variant.modal_app_name}-generate-input4-expected_output.json",
        ),
    ]


def generate(hyper_only: bool = False) -> None:
    """
    Configures and runs the fixture generator for MPNN model.

    Args:
        hyper_only: If True, only generate fixtures for hyper-mpnn variant
    """
    fixture_generation_suite.variant_test_mappings[0].test_cases = _build_test_cases()

    if hyper_only:
        # Create a custom generator that only processes hyper variant
        from models.commons.testing.runner import _variant_matches_mapping_filter

        generator = FixtureGenerator(fixture_generation_suite)

        # Get all variants and filter for hyper
        all_variants = generator.suite.model_family.resolved_variants
        hyper_variants = [
            v for v in all_variants if "hyper" in v.modal_app_name.lower()
        ]

        if not hyper_variants:
            logger.warning("❌ No hyper-mpnn variant found in resolved variants")
            return

        logger.info(
            "🎯 Generating fixtures only for: %s",
            [v.modal_app_name for v in hyper_variants],
        )

        # Manually process only hyper variants
        written_inputs: set[str] = set()

        for variant in hyper_variants:
            test_cases = generator._get_matching_test_cases(
                variant, _variant_matches_mapping_filter
            )
            if not test_cases:
                continue

            logger.info("\n⚙️  Processing variant '%s'...", variant.modal_app_name)
            generator._write_input_files(test_cases, variant, written_inputs)

            from models.commons.testing.runner import setup_and_get_local_model_instance

            logger.info(
                "  - Setting up Modal instance for variant '%s'...",
                variant.modal_app_name,
            )
            model_instance, app_object = setup_and_get_local_model_instance(
                generator.suite, variant
            )

            logger.info(
                "  - Generating fixture outputs for variant '%s'...",
                variant.modal_app_name,
            )
            generator._generate_output_files(
                model_instance, app_object, test_cases, variant
            )

            logger.info(
                "✅ Wrote all output fixtures for variant '%s'.", variant.modal_app_name
            )

        logger.info("\n--- ✅ HyperMPNN fixture generation complete! ---")
    else:
        generator = FixtureGenerator(fixture_generation_suite)
        generator.generate()


if __name__ == "__main__":
    import sys

    # Usage:
    #   python models/mpnn/fixture.py          # Generate for all variants
    #   python models/mpnn/fixture.py --hyper   # Generate only for hyper-mpnn
    hyper_only = "--hyper" in sys.argv or "-h" in sys.argv

    if hyper_only:
        logger.info("🎯 Generating fixtures only for hyper-mpnn variant...")
    else:
        logger.info("🚀 Generating fixtures for all MPNN variants...")

    generate(hyper_only=hyper_only)
