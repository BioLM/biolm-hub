from collections.abc import Callable
from typing import Any, Optional, Union

from pydantic import BaseModel

from models.commons.model.config import ModelFamily

# --- Unified test configuration schemas ---


class ActionTestCase(BaseModel):
    """
    Defines a single, reusable test case for a model action.
    This is the data structure used in fixture.py.
    """

    # The name of the method in the app.py class to call (e.g., "predict").
    action_name: str

    # Path to the input data file in R2, relative to the model's test data directory.
    # Can also be a dict or Pydantic model for programmatic input generation.
    input_fixture: Union[str, dict, BaseModel]

    # Optional: Path to the expected output file for integration tests.
    # Can be a string template, e.g., "{variant.name}_output.json", which the
    # test runner will format with the properties of the ResolvedVariant.
    expected_output_fixture: Optional[str] = None

    # Optional: Filename template for programmatic inputs when using FixtureGenerator.
    input_filename_template: Optional[str] = None

    # Optional: Tolerances for numerical comparisons in integration tests.
    tolerances: dict[str, Any] = {}

    # Optional custom validation function for the response.
    validator: Optional[Callable[[Any, Optional[dict]], None]] = None

    # A dictionary of kwargs to pass to the .remote() function.
    remote_fn_kwargs: Optional[dict[str, Any]] = None

    # Optional: Override the request schema from ModelFamily for this specific test case.
    # Useful for actions that need different schemas based on variant (e.g., ProstT5).
    # When specified, this schema will be used instead of the ModelFamily's default schema.
    request_schema: Optional[type[BaseModel]] = None


class VariantTestMapping(BaseModel):
    """
    Maps a specific variant configuration to a list of its applicable test cases.
    This is the object that defines the "cross" between variants and inputs.
    """

    # An empty dict {} means this mapping applies to ALL variants.
    # A specific dict like {"MODEL_TYPE": "antibody"} targets a specific variant or subset.
    variant_config: dict[str, Any]
    test_cases: list[ActionTestCase]


class TestSuite(BaseModel):
    """
    Links a ModelFamily to a list of its variant-specific test mappings.
    The test runner will use this to generate the full test matrix.
    """

    model_config = {"protected_namespaces": ()}  # Allow 'model_' fields
    __test__ = False  # tell pytest "this isn't a test class"

    model_family: ModelFamily
    variant_test_mappings: list[VariantTestMapping]

    # Controls the R2 path subfolder: test-data/{r2_fixture_subdir}/{slug}.
    # Use "models" for regular models, "finetune" for finetune inference models.
    r2_fixture_subdir: str

    # Override the auto-detected app module path. By default, the runner
    # constructs "models.{slug}.app". Training inference apps should set this
    # to their module path, e.g. "training.xgboost.infer.app".
    app_module: Optional[str] = None
