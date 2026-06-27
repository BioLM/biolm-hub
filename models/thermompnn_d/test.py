from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.thermompnn_d.config import MODEL_FAMILY
from models.thermompnn_d.fixture import INPUT1, INPUT2, INPUT3, INPUT4, INPUT5, INPUT6


def _validate_thermompnn_d_predict(actual_output: dict, _expected_output: dict = None):
    """Validate ThermoMPNN-D predict output with mode-specific field checks."""
    assert "results" in actual_output, "Response missing 'results' key"
    assert len(actual_output["results"]) > 0, "Results list is empty"
    for result in actual_output["results"]:
        assert "mutation" in result, "Result missing 'mutation' key"
        assert "ddg" in result, "Result missing 'ddg' key"
        assert isinstance(result["ddg"], int | float), "ddg must be numeric"

        # Check mode-specific fields based on mutation format
        mutation = result["mutation"]
        if ":" in mutation:
            required = [
                "position1",
                "position2",
                "wildtype1",
                "wildtype2",
                "mutation_aa1",
                "mutation_aa2",
            ]
            mode = "Double"
        else:
            required = ["position", "wildtype", "mutation_aa"]
            mode = "Single"

        for field in required:
            assert field in result, f"{mode} mutation missing '{field}': {mutation}"


# ThermoMPNN-D test suite - single variant
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
                    validator=_validate_thermompnn_d_predict,
                ),
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=INPUT2,
                    validator=_validate_thermompnn_d_predict,
                ),
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=INPUT3,
                    validator=_validate_thermompnn_d_predict,
                ),
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=INPUT4,
                    validator=_validate_thermompnn_d_predict,
                ),
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=INPUT5,
                    validator=_validate_thermompnn_d_predict,
                ),
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=INPUT6,
                    validator=_validate_thermompnn_d_predict,
                ),
            ],
        )
    ],
)


# Generate integration tests (marked with @pytest.mark.integration)
generate_tests_from_suite(test_suite, test_type="integration")

# Generate deployment tests (marked with @pytest.mark.deployment)
generate_tests_from_suite(test_suite, test_type="deployment")

# Usage:
#   pytest models/thermompnn_d/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/thermompnn_d/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/thermompnn_d/test.py -n auto --no-cov -v -s                 # both
