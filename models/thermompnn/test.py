from typing import Optional

from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.thermompnn.config import MODEL_FAMILY
from models.thermompnn.fixture import INPUT1, INPUT2, INPUT3, INPUT4


def _validate_thermompnn_predict(
    actual_output: dict, _expected_output: Optional[dict] = None
):
    """Basic validation for ThermoMPNN predict output - check structure."""
    assert "results" in actual_output, "Response missing 'results' key"
    assert len(actual_output["results"]) > 0, "Results list is empty"
    for result in actual_output["results"]:
        assert "mutation" in result, "Result missing 'mutation' key"
        assert "position" in result, "Result missing 'position' key"
        assert "wildtype" in result, "Result missing 'wildtype' key"
        assert "mutation_aa" in result, "Result missing 'mutation_aa' key"
        assert "ddg" in result, "Result missing 'ddg' key"
        assert isinstance(result["ddg"], int | float), "ddg must be numeric"


# ThermoMPNN test suite - single variant
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={},  # Empty dict means applies to all variants (single variant here)
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=INPUT1,
                    validator=_validate_thermompnn_predict,
                ),
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=INPUT2,
                    validator=_validate_thermompnn_predict,
                ),
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=INPUT3,
                    validator=_validate_thermompnn_predict,
                ),
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=INPUT4,
                    validator=_validate_thermompnn_predict,
                ),
            ],
        )
    ],
)


# Generate integration tests (marked with @pytest.mark.integration)
test_thermompnn_integration = generate_tests_from_suite(
    test_suite, test_type="integration"
)

# Generate deployment tests (marked with @pytest.mark.deployment)
test_thermompnn_deployment = generate_tests_from_suite(
    test_suite, test_type="deployment"
)

# Usage:
#   pytest models/thermompnn/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/thermompnn/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/thermompnn/test.py -n auto --no-cov -v -s                 # both
