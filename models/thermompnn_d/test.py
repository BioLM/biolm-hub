from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.thermompnn_d.config import MODEL_FAMILY
from models.thermompnn_d.fixture import INPUT1, INPUT2, INPUT3, INPUT4, INPUT5, INPUT6

# ThermoMPNN-D is a DETERMINISTIC ΔΔG predictor (single/double-mutation and SSM
# scans; no sampling), so integration cases numerically compare the ddG output
# against the R2 golden via DictComparator instead of a structural-only validator.
# The mode-specific string/int fields (mutation, position*, wildtype*, mutation_aa*)
# are compared exactly by DictComparator; ddG is compared with rel_tol=1e-4 to match
# the sibling ΔΔG model `spurs` (see models/spurs/test.py). Because both the golden
# and the live response are serialized by the same code path, optional fields left
# `None` (e.g. position1/position2 for single mutations) line up on both sides. The
# expected-output filenames below are exactly the goldens written by fixture.py.
_DDG_TOLERANCES = {"rel_tol": 1e-4}  # tight numerical tolerance for ΔΔG (kcal/mol)

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
                    expected_output_fixture="thermompnn-d-predict-input1-expected_output.json",
                    tolerances=_DDG_TOLERANCES,
                ),
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=INPUT2,
                    expected_output_fixture="thermompnn-d-predict-input2-expected_output.json",
                    tolerances=_DDG_TOLERANCES,
                ),
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=INPUT3,
                    expected_output_fixture="thermompnn-d-predict-input3-expected_output.json",
                    tolerances=_DDG_TOLERANCES,
                ),
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=INPUT4,
                    expected_output_fixture="thermompnn-d-predict-input4-expected_output.json",
                    tolerances=_DDG_TOLERANCES,
                ),
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=INPUT5,
                    expected_output_fixture="thermompnn-d-predict-input5-expected_output.json",
                    tolerances=_DDG_TOLERANCES,
                ),
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=INPUT6,
                    expected_output_fixture="thermompnn-d-predict-input6-expected_output.json",
                    tolerances=_DDG_TOLERANCES,
                ),
            ],
        )
    ],
)


# Generate integration tests (marked with @pytest.mark.integration)
test_thermompnn_d_integration = generate_tests_from_suite(
    test_suite, test_type="integration"
)

# Generate deployment tests (marked with @pytest.mark.deployment)
test_thermompnn_d_deployment = generate_tests_from_suite(
    test_suite, test_type="deployment"
)

# Usage:
#   pytest models/thermompnn_d/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/thermompnn_d/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/thermompnn_d/test.py -n auto --no-cov -v -s                 # both
