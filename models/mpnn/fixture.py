from models.commons.core.logging import get_logger
from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.mpnn.config import MODEL_FAMILY

logger = get_logger(__name__)

# Test input/output filenames (manually created and stored in R2)
# MPNN uses multiple input files for all variants
INPUT1 = "input1.json"
INPUT2 = "input2.json"
INPUT3 = "input3.json"
INPUT4 = "input4.json"
# INPUT5 = "input5.json"

# Use the same test suite as test.py for fixture generation
# This will generate fixtures for ALL variants including hyper
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single mapping that applies to ALL variants (including hyper)
        VariantTestMapping(
            variant_config={},  # Empty dict means applies to ALL variants
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=INPUT1,
                    expected_output_fixture="{variant.modal_app_name}-generate-input1-expected_output.json",
                ),
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=INPUT2,
                    expected_output_fixture="{variant.modal_app_name}-generate-input2-expected_output.json",
                ),
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=INPUT3,
                    expected_output_fixture="{variant.modal_app_name}-generate-input3-expected_output.json",
                ),
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=INPUT4,
                    expected_output_fixture="{variant.modal_app_name}-generate-input4-expected_output.json",
                ),
            ],
        )
    ],
)


def generate(hyper_only: bool = False):
    """
    Configures and runs the fixture generator for MPNN model.

    Args:
        hyper_only: If True, only generate fixtures for hyper-mpnn variant
    """
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
        written_inputs = set()

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
