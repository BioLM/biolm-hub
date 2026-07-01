import os
import sys
import time
from collections.abc import Callable
from importlib import import_module
from typing import Any, Optional, cast

import modal
import pytest
from pydantic import BaseModel, ValidationError

from models.commons.model.config import ResolvedVariant
from models.commons.storage.r2 import read_json_from_r2
from models.commons.testing.config import (
    ActionTestCase,
    TestSuite,
)
from models.commons.util.config import (
    r2_bucket_name,
    r2_test_data_dir,
)

### COMMON TEST UTILS


def _fixture_r2_path(r2_fixture_subdir: str, slug: str, filename: str) -> str:
    """Resolve a fixture filename to its R2 key.

    A filename beginning with ``shared/`` references the cross-model shared
    asset library at ``test-data/shared/...`` (see
    ``models.commons.testing.shared_assets``); anything else is per-model under
    ``test-data/<subdir>/<slug>/``.
    """
    if filename.startswith("shared/"):
        return f"{r2_test_data_dir}/{filename}"
    return f"{r2_test_data_dir}/{r2_fixture_subdir}/{slug}/{filename}"


def _validate_log_prob(
    actual_output: dict[str, Any], _expected_output: Optional[dict[str, Any]] = None
) -> None:
    """Consolidated validator for log probability output across all models."""
    # All models wrap batch output under the canonical `results` key.
    assert "results" in actual_output, "Response missing the 'results' key"
    assert len(actual_output["results"]) > 0, "Results list is empty"

    # Validate structure of each result
    for result in actual_output["results"]:
        assert "log_prob" in result, "Result missing 'log_prob' key"
        assert isinstance(result["log_prob"], int | float), "log_prob must be numeric"
        assert result["log_prob"] < 0, "log_prob should be negative"


### UNIFIED TEST UTILS


def _validate_with_pydantic_schema(
    input_data: Any, schema: Optional[type[BaseModel]], context_name: str
) -> Any:
    """Common function to validate data with Pydantic schema, handling v1/v2 compatibility."""
    if schema is None:
        print("  - Sending raw JSON (no schema validation)")
        return input_data

    print(f"  - Validating input with schema: {schema.__name__}")
    try:
        # Handle both Pydantic v1 and v2 schemas compatibility
        # SADIE uses Pydantic v1 schemas while other models use v2
        if hasattr(schema, "model_validate"):
            # Pydantic v2
            return schema.model_validate(input_data)
        else:
            # Pydantic v1 - use parse_obj
            return schema.parse_obj(input_data)
    except ValidationError as e:
        pytest.fail(
            f"❌ Input data failed Pydantic validation for {context_name}. Error: {e}"
        )


def _resolve_app_module_name(suite: TestSuite) -> str:
    """Resolve the app module name from the suite configuration."""
    if suite.app_module:
        return suite.app_module
    module_package_name = suite.model_family.base_model_slug.replace("-", "_")
    return f"models.{module_package_name}.app"


def setup_and_get_local_model_instance(
    suite: TestSuite, variant: ResolvedVariant
) -> tuple[Any, Any]:
    """Handles environment setup and dynamically imports the local app module."""
    os.environ.update(variant.env_vars)

    module_name = _resolve_app_module_name(suite)
    if module_name in sys.modules:
        del sys.modules[module_name]  # Evict for fresh import

    app_module = import_module(module_name)

    # Find the class marked with our decorator
    for _, obj in app_module.__dict__.items():
        if hasattr(obj, "_is_biolm_model_class"):
            return obj(), app_module.app
    pytest.fail(
        f"Could not find a class marked with @biolm_model_class in {module_name}"
    )


def _load_and_validate_payload(
    suite: TestSuite, case: ActionTestCase, variant: ResolvedVariant
) -> Any:
    """Handles loading data from R2 and validating with Pydantic."""
    if isinstance(case.input_fixture, str):
        # Load from R2 - format template if needed (supports both templated and non-templated inputs)
        try:
            input_filename = case.input_fixture.format(variant=variant)
        except (KeyError, AttributeError):
            # No template formatting needed (e.g., "predict_input.json")
            input_filename = case.input_fixture
        path = _fixture_r2_path(
            suite.r2_fixture_subdir,
            suite.model_family.base_model_slug,
            input_filename,
        )
        input_data = read_json_from_r2(r2_bucket_name, path)
    else:
        # Programmatic input generation - handle dicts and Pydantic models
        if isinstance(case.input_fixture, dict):
            # Already a dict - use it directly
            input_data = case.input_fixture
        else:
            input_data = case.input_fixture.model_dump()

    # Determine which schema to use for validation. ``request_schema`` is an
    # optional field that defaults to None, so an *unset* case is
    # indistinguishable from an explicit ``None`` via attribute access. We
    # discriminate intent with ``model_fields_set`` (the set of fields the case
    # actually provided):
    # - request_schema unset      -> validate against the ModelFamily default
    # - request_schema=None        -> explicit opt-out: send raw JSON (no validation)
    # - request_schema=SomeSchema  -> per-case override
    if "request_schema" not in case.model_fields_set:
        action_schema = next(
            a for a in suite.model_family.action_schemas if a.name == case.action_name
        )
        request_schema = action_schema.request_schema
        print(f"  - Using ModelFamily schema: {request_schema.__name__}")
    elif case.request_schema is None:
        request_schema = None
    else:
        request_schema = case.request_schema
        print(f"  - Using override schema: {request_schema.__name__}")

    # Use consolidated validation function
    test_context = f"[{variant.modal_app_name}] -> {case.action_name}"
    return _validate_with_pydantic_schema(input_data, request_schema, test_context)


def execute_integration_test_case(
    suite: TestSuite, variant: ResolvedVariant, case: ActionTestCase
) -> None:
    """Generic function to execute a single integration test case."""
    test_name = f"INTEGRATION [{variant.modal_app_name}] -> {case.action_name}"
    print(f"\n🧪 Running Test: {test_name}")

    # 1. Setup and get local model instance
    model_instance, app_object = setup_and_get_local_model_instance(suite, variant)

    # 2. Load and validate input payload
    payload = _load_and_validate_payload(suite, case, variant)

    # 3. Load expected output ("Golden File")
    expected_output = None
    if case.expected_output_fixture:
        filename = case.expected_output_fixture.format(variant=variant)
        path = _fixture_r2_path(
            suite.r2_fixture_subdir,
            suite.model_family.base_model_slug,
            filename,
        )
        expected_output = read_json_from_r2(r2_bucket_name, path)

    # 4. Execute the remote method with retry logic (matching old system)
    MAX_ATTEMPTS = 2
    actual_output: Optional[dict[str, Any]] = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            final_kwargs = case.remote_fn_kwargs or {"_skip_cache": True}
            fn = getattr(model_instance, case.action_name)
            print(
                f"  - Calling local method '{case.action_name}' within app.run() (Attempt {attempt + 1}/2)..."
            )
            # Include modal.enable_output() like old system
            with modal.enable_output(), app_object.run():
                actual_output = fn.remote(payload, **final_kwargs)
            print("  - Local call successful.")
            break  # Success, exit retry loop
        except Exception as e:
            error_str = str(e)
            # Check if it's a retryable error and if we have retries left
            is_retryable = (
                # Modal image build failures
                ("Image build for" in error_str and "failed" in error_str)
                # Empty exception messages (infrastructure failures)
                or error_str.strip() == ""
                # Timeout-related errors
                or "timeout" in error_str.lower()
                or "timed out" in error_str.lower()
            )

            if is_retryable and (attempt + 1) < MAX_ATTEMPTS:
                print(
                    "  - ⚠️ WARNING: Modal infrastructure issue detected. Retrying in 10 seconds..."
                )
                print(
                    f"     Error: {error_str if error_str else '(empty error message)'}"
                )
                time.sleep(10)
                continue  # Retry
            else:
                # If it's a different error or the retry also failed, fail immediately
                error_msg = (
                    error_str
                    if error_str
                    else "(empty error message - likely infrastructure failure)"
                )
                pytest.fail(
                    f"❌ Local method call failed for {test_name}. Error: {error_msg}"
                )

    # 5. Validate the output
    # By this point either the call above succeeded (actual_output was assigned) or
    # a retryable failure exhausted its attempts and hit the pytest.fail() (NoReturn)
    # above, which exits before we get here — so actual_output is never really None.
    assert actual_output is not None, "actual_output must be set by the call above"
    try:
        if case.validator:
            case.validator(actual_output, expected_output)
        elif expected_output is not None:
            # Compare outputs using DictComparator
            from models.commons.testing.comparator import DictComparator

            comparator = DictComparator(**case.tolerances)
            are_close = comparator.compare(actual_output, expected_output)

            if not are_close:
                # Use comparator's error formatting for detailed failure message
                pytest.fail(
                    f"❌ Validation Failed for {test_name}: {comparator.format_error_message()}"
                )
        else:
            pytest.fail(
                f"❌ No validator or expected_output_fixture provided for {test_name}."
            )

        print(f"✅ PASS: {test_name}")
    except AssertionError as e:
        # This should not be reached now since we handle the assertion above
        pytest.fail(f"❌ Validation Failed for {test_name}: {e}")


def _default_deployment_validator(
    actual_output: dict[str, Any], _expected_output: Optional[dict[str, Any]] = None
) -> None:
    """Default check: ensure the canonical 'results' key exists and is not empty."""
    # All models wrap batch output under the canonical `results` key.
    print(
        "  - Using default deployment validator (checking for non-empty 'results' key)."
    )
    assert (
        "results" in actual_output
    ), "Validation failed: Response is missing the 'results' key."
    assert actual_output["results"], "Validation failed: 'results' key is empty."


def _get_model_class_from_deployment(suite: TestSuite, variant: ResolvedVariant) -> Any:
    """Get the model class from a deployed Modal app using decorator discovery."""
    # Import the app module to discover the decorated class
    module_name = _resolve_app_module_name(suite)
    app_module = import_module(module_name)

    # Find the class marked with our decorator
    for name, obj in app_module.__dict__.items():
        if hasattr(obj, "_is_biolm_model_class"):
            # Use the discovered class name instead of string manipulation
            ModelClass = modal.Cls.from_name(variant.modal_app_name, name)
            return ModelClass()


def execute_deployment_test_case(
    suite: TestSuite, variant: ResolvedVariant, case: ActionTestCase
) -> None:
    """Generic function to execute a single deployment test case."""
    test_name = f"DEPLOYMENT [{variant.modal_app_name}] -> {case.action_name}"
    print(f"\n🧪 Running Test: {test_name}")

    # 1. Load and validate input payload
    payload = _load_and_validate_payload(suite, case, variant)

    # 2. Get deployed model instance using decorator discovery
    model_instance = _get_model_class_from_deployment(suite, variant)

    # 3. Execute the remote method
    final_kwargs = case.remote_fn_kwargs or {"_skip_cache": True}
    fn = getattr(model_instance, case.action_name)
    with modal.enable_output():
        actual_output = fn.remote(payload, **final_kwargs)

    # 4. Validate the output (use case validator when provided, else default)
    validator = case.validator or _default_deployment_validator
    validator(actual_output, None)
    print(f"✅ PASS: {test_name}")


def _variant_matches_mapping_filter(
    variant: ResolvedVariant, mapping_config: dict[str, Any]
) -> bool:
    """Check if a variant matches the mapping's filter."""
    return all(
        item in variant._variant_config.items() for item in mapping_config.items()
    )


def _is_case_valid_for_test_type(case: ActionTestCase, test_type: str) -> bool:
    """Check if a test case is valid for the given test type."""
    if test_type in ("integration", "slow"):
        # Integration/slow tests require expected_output_fixture OR validator
        return bool(case.expected_output_fixture or case.validator)
    elif test_type == "deployment":
        # Deployment tests can run with or without expected outputs
        return True
    return False


def _generate_test_id(case: ActionTestCase, variant: ResolvedVariant) -> str:
    """Generate a unique, readable ID for pytest output."""
    if isinstance(case.input_fixture, str):
        # Format template if needed, then extract base name
        try:
            formatted_input = case.input_fixture.format(variant=variant)
        except (KeyError, AttributeError):
            # No template formatting needed
            formatted_input = case.input_fixture
        input_part = formatted_input.split(".")[0]
    else:
        input_part = "programmatic"

    if variant.name:  # Multi-variant model
        return f"{variant.name}-{case.action_name}-{input_part}"
    else:  # Single-variant model - no leading dash
        return f"{case.action_name}-{input_part}"


def _collect_test_params(suite: TestSuite, test_type: str) -> list[Any]:
    """Collect all test parameters for the given test suite and type."""
    test_params = []

    for mapping in suite.variant_test_mappings:
        for variant in suite.model_family.resolved_variants:
            if _variant_matches_mapping_filter(variant, mapping.variant_config):
                for case in mapping.test_cases:
                    if _is_case_valid_for_test_type(case, test_type):
                        test_id = _generate_test_id(case, variant)
                        test_params.append(pytest.param(variant, case, id=test_id))

    return test_params


def _apply_test_type_marker(
    test_fn: Callable[..., Any], test_type: str
) -> Callable[..., Any]:
    """Apply the pytest marker that matches the test type (no-op if unknown)."""
    if test_type == "integration":
        return cast(Callable[..., Any], pytest.mark.integration(test_fn))
    if test_type == "slow":
        return cast(Callable[..., Any], pytest.mark.slow(test_fn))
    if test_type == "deployment":
        return cast(Callable[..., Any], pytest.mark.deployment(test_fn))
    return test_fn


def _create_test_template(suite: TestSuite, test_type: str) -> Callable[..., Any]:
    """Create the test template function with appropriate markers."""

    def test_template(variant: ResolvedVariant, case: ActionTestCase) -> None:
        if test_type in ("integration", "slow"):
            execute_integration_test_case(suite, variant, case)
        elif test_type == "deployment":
            execute_deployment_test_case(suite, variant, case)
        else:
            pytest.fail(f"Unknown test_type: {test_type}")

    return _apply_test_type_marker(test_template, test_type)


def _create_empty_suite_test(test_type: str) -> Callable[..., Any]:
    """Return a single test that skips when a suite collects no cases.

    An empty ``pytest.mark.parametrize`` list silently yields zero tests, so a
    misconfigured suite (Modal/R2 absent, missing fixtures) would look "green"
    while running nothing. Returning one skipping test keeps collection
    observable: ``--collect-only`` always reports >=1 item per generated test.
    """

    def test_template() -> None:
        pytest.skip(
            f"no {test_type} test cases collected — check Modal/R2 config / fixtures"
        )

    return _apply_test_type_marker(test_template, test_type)


def generate_tests_from_suite(suite: TestSuite, test_type: str) -> Callable[..., Any]:
    """Build and return a parametrized pytest test function for a ``TestSuite``.

    Assign the result to a module-level ``test_*`` name so pytest collects it::

        test_esm2_integration = generate_tests_from_suite(suite, test_type="integration")

    Returning the function (instead of injecting it into the caller's module
    globals) makes every ``models/<model>/test.py`` a first-class pytest
    collectible: ``pytest --collect-only`` works without running anything, IDE
    discovery and ``-k`` selection work, and an empty suite surfaces as a skip
    rather than silently collecting zero tests.
    """
    test_params = _collect_test_params(suite, test_type)

    if not test_params:
        return _create_empty_suite_test(test_type)

    test_template = _create_test_template(suite, test_type)
    return cast(
        Callable[..., Any],
        pytest.mark.parametrize("variant, case", test_params)(test_template),
    )
