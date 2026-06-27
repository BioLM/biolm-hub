from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.immunefold.config import MODEL_FAMILY
from models.immunefold.fixture import (
    ANTIBODY_PREDICT_INPUT,
    ANTIBODY_PREDICT_OUTPUT,
    ANTIGEN_PREDICT_INPUT,
    ANTIGEN_PREDICT_OUTPUT,
    NANOBODY_PREDICT_INPUT,
    NANOBODY_PREDICT_OUTPUT,
    TCR_PREDICT_INPUT,
    TCR_PREDICT_OUTPUT,
)

# ImmuNeFold test suite - variant-specific test mappings based on model type
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Antibody variant - has 3 input types
        VariantTestMapping(
            variant_config={"MODEL_TYPE": "antibody"},
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=ANTIGEN_PREDICT_INPUT,
                    expected_output_fixture=ANTIGEN_PREDICT_OUTPUT,
                    tolerances={"rel_tol": 1e-4, "pdb_rmsd_threshold": 1e-4},
                ),
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=ANTIBODY_PREDICT_INPUT,
                    expected_output_fixture=ANTIBODY_PREDICT_OUTPUT,
                    tolerances={"rel_tol": 1e-4, "pdb_rmsd_threshold": 1e-4},
                ),
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=NANOBODY_PREDICT_INPUT,
                    expected_output_fixture=NANOBODY_PREDICT_OUTPUT,
                    tolerances={"rel_tol": 1e-4, "pdb_rmsd_threshold": 1e-4},
                ),
            ],
        ),
        # TCR variant - has 1 input type
        VariantTestMapping(
            variant_config={"MODEL_TYPE": "tcr"},
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=TCR_PREDICT_INPUT,
                    expected_output_fixture=TCR_PREDICT_OUTPUT,
                    tolerances={"rel_tol": 1e-4, "pdb_rmsd_threshold": 1e-4},
                ),
            ],
        ),
    ],
)


# Generate integration tests (marked with @pytest.mark.integration)
test_immunefold_integration = generate_tests_from_suite(
    test_suite, test_type="integration"
)

# Generate deployment tests (marked with @pytest.mark.deployment)
test_immunefold_deployment = generate_tests_from_suite(
    test_suite, test_type="deployment"
)

# Usage:
#   pytest models/immunefold/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/immunefold/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/immunefold/test.py -n auto --no-cov -v -s                 # both
