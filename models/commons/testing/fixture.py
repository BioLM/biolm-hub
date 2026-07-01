from collections.abc import Callable
from typing import Any, Optional

import modal

from models.commons.model.config import ResolvedVariant
from models.commons.storage.r2 import read_json_from_r2, write_data_to_r2
from models.commons.testing.config import ActionTestCase, TestSuite
from models.commons.testing.runner import (
    _fixture_r2_path,
    setup_and_get_local_model_instance,
)
from models.commons.util.config import (
    r2_bucket_name,
    r2_test_data_dir,
)


class FixtureGenerator:
    """A fixture generator that works with TestSuite and ActionTestCase objects."""

    def __init__(self, suite: TestSuite):
        self.suite = suite
        self.r2_base_path = f"{r2_test_data_dir}/{suite.r2_fixture_subdir}/{suite.model_family.base_model_slug}"
        self.test_cases: list[ActionTestCase] = []

    def add_test_case(self, test_case: ActionTestCase) -> None:
        """Registers a new ActionTestCase to be run."""
        self.test_cases.append(test_case)

    def _get_matching_test_cases(
        self,
        variant: ResolvedVariant,
        mapping_filter_func: Callable[[ResolvedVariant, dict[str, Any]], bool],
    ) -> Optional[list[ActionTestCase]]:
        """Get test cases that match the given variant."""
        matching_test_cases: list[ActionTestCase] = []
        variant_matches = False

        for mapping in self.suite.variant_test_mappings:
            if mapping_filter_func(variant, mapping.variant_config):
                variant_matches = True
                matching_test_cases.extend(mapping.test_cases)

        # Include legacy test cases if present
        if variant_matches and self.test_cases:
            print(
                "  - Warning: Test cases added via add_test_case() don't respect variant filtering"
            )
            matching_test_cases.extend(self.test_cases)

        return matching_test_cases if variant_matches else None

    def _write_input_files(
        self,
        test_cases: list[ActionTestCase],
        variant: ResolvedVariant,
        written_inputs: set[str],
    ) -> None:
        """Write input files for the given test cases."""
        for case in test_cases:
            # Skip file-based inputs - they should already exist
            if isinstance(case.input_fixture, str):
                continue

            # Programmatic input - convert to JSON and upload
            try:
                # A None template intentionally raises AttributeError here, caught
                # below to fall back to the (also None) raw template value.
                input_path = case.input_filename_template.format(  # type: ignore[union-attr]
                    variant=variant
                )
            except (KeyError, AttributeError):
                input_path = case.input_filename_template

            if input_path not in written_inputs:
                r2_input_path = f"{self.r2_base_path}/{input_path}"
                if isinstance(case.input_fixture, dict):
                    input_data_dict = case.input_fixture
                else:
                    input_data_dict = case.input_fixture.model_dump()
                write_data_to_r2(r2_bucket_name, r2_input_path, input_data_dict)
                written_inputs.add(input_path)

    def _generate_output_files(
        self,
        model_instance: Any,
        app_object: Any,
        test_cases: list[ActionTestCase],
        variant: ResolvedVariant,
    ) -> None:
        """Generate output files by calling the app methods."""
        with modal.enable_output(), app_object.run():
            for case in test_cases:
                print(f"    - Generating: {case.action_name}")

                # Load input data from R2 if input_fixture is a string (filename).
                # Use the shared-aware resolver so a "shared/..." input reads from
                # the same key the runner reads (test-data/shared/...). Outputs are
                # always per-model, so they stay on self.r2_base_path below.
                if isinstance(case.input_fixture, str):
                    # Format template if needed
                    try:
                        input_filename = case.input_fixture.format(variant=variant)
                    except (KeyError, AttributeError):
                        input_filename = case.input_fixture
                    input_path = _fixture_r2_path(
                        self.suite.r2_fixture_subdir,
                        self.suite.model_family.base_model_slug,
                        input_filename,
                    )
                    input_data = read_json_from_r2(r2_bucket_name, input_path)
                else:
                    # Already a dict or Pydantic model - convert to dict
                    if isinstance(case.input_fixture, dict):
                        input_data = case.input_fixture
                    else:
                        input_data = case.input_fixture.model_dump()

                # Call the method with the loaded input data
                fn = getattr(model_instance, case.action_name)
                actual_output = fn.remote(input_data, _skip_cache=True)

                # Check if response contains a valid response key - if not, it's likely an error
                # Common response keys: 'results', 'sequences', 'data', etc.
                common_response_keys = ["results", "sequences", "data"]
                has_valid_response = False
                if isinstance(actual_output, dict):
                    has_valid_response = any(
                        key in actual_output for key in common_response_keys
                    )
                else:
                    has_valid_response = any(
                        hasattr(actual_output, key) for key in common_response_keys
                    )

                if not has_valid_response:
                    print(
                        "\n❌ ERROR: Response doesn't contain a valid response key/attribute."
                    )
                    print(f"    Expected one of: {common_response_keys}")
                    print("    This typically indicates an error response.")
                    print(f"\n    Full response: {actual_output}")
                    print("\n⚠️  Please fix the model implementation and try again.")
                    raise RuntimeError(
                        f"Invalid response - missing valid response key. Response: {actual_output}"
                    )

                # Write the output to R2
                try:
                    # A None fixture intentionally raises AttributeError here, caught
                    # below to fall back to the (also None) raw value.
                    output_path = case.expected_output_fixture.format(  # type: ignore[union-attr]
                        variant=variant
                    )
                except (KeyError, AttributeError):
                    output_path = case.expected_output_fixture

                r2_output_path = f"{self.r2_base_path}/{output_path}"
                write_data_to_r2(r2_bucket_name, r2_output_path, actual_output)

    def generate(self) -> None:
        """Runs the full fixture generation process using the TestSuite system."""
        print(
            f"--- 🚀 Generating fixtures for {self.suite.model_family.base_model_slug} ---"
        )

        from models.commons.testing.runner import _variant_matches_mapping_filter

        written_inputs: set[str] = (
            set()
        )  # Track inputs to avoid re-uploading variant-agnostic files

        for variant in self.suite.model_family.resolved_variants:
            # Get matching test cases for this variant
            test_cases = self._get_matching_test_cases(
                variant, _variant_matches_mapping_filter
            )
            if not test_cases:
                continue  # Skip variants that don't match any filter

            print(f"\n⚙️  Processing variant '{variant.modal_app_name}'...")

            # 1. Write input files for this variant
            self._write_input_files(test_cases, variant, written_inputs)

            # 2. Setup Modal instance
            print(
                f"  - Setting up Modal instance for variant '{variant.modal_app_name}'..."
            )
            model_instance, app_object = setup_and_get_local_model_instance(
                self.suite, variant
            )

            # 3. Generate output files by calling the app methods
            print(
                f"  - Generating fixture outputs for variant '{variant.modal_app_name}'..."
            )
            self._generate_output_files(model_instance, app_object, test_cases, variant)

            print(
                f"✅ Wrote all output fixtures for variant '{variant.modal_app_name}'."
            )

        print("\n--- ✅ All fixture generation complete! ---")
