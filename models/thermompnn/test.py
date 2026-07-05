from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.thermompnn.config import MODEL_FAMILY
from models.thermompnn.fixture import INPUT1, INPUT2, INPUT3, INPUT4

# ThermoMPNN is a DETERMINISTIC ΔΔG predictor (single forward pass, no sampling),
# so integration cases numerically compare the ddG output against the R2 golden via
# DictComparator instead of a structural-only validator. rel_tol=1e-4 matches the
# sibling ΔΔG model `spurs` (see models/spurs/test.py). The expected-output filenames
# below are exactly the goldens written by fixture.py's `generate()`.
_DDG_TOLERANCES = {"rel_tol": 1e-4}  # tight numerical tolerance for ΔΔG (kcal/mol)

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
                    expected_output_fixture="thermompnn-predict-input1-expected_output.json",
                    tolerances=_DDG_TOLERANCES,
                ),
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=INPUT2,
                    expected_output_fixture="thermompnn-predict-input2-expected_output.json",
                    tolerances=_DDG_TOLERANCES,
                ),
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=INPUT3,
                    expected_output_fixture="thermompnn-predict-input3-expected_output.json",
                    tolerances=_DDG_TOLERANCES,
                ),
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=INPUT4,
                    expected_output_fixture="thermompnn-predict-input4-expected_output.json",
                    tolerances=_DDG_TOLERANCES,
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
