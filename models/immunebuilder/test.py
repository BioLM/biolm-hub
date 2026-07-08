from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.immunebuilder.config import MODEL_FAMILY
from models.immunebuilder.fixture import PREDICT_INPUT_TPL, PREDICT_OUTPUT_TPL

# ImmuneBuilder test suite - all variants use the same test pattern
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single mapping that applies to ALL variants
        VariantTestMapping(
            variant_config={},  # Empty dict means applies to ALL variants
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=PREDICT_INPUT_TPL,
                    expected_output_fixture=PREDICT_OUTPUT_TPL,
                    # 1.5 Å: accounts for platform/CUDA numeric differences in OpenMM energy minimization
                    tolerances={"rel_tol": 1e-4, "pdb_rmsd_threshold": 1.5},
                ),
            ],
        )
    ],
)


# Generate integration tests (marked with @pytest.mark.integration)
test_immunebuilder_integration = generate_tests_from_suite(
    test_suite, test_type="integration"
)

# Generate deployment tests (marked with @pytest.mark.deployment)
test_immunebuilder_deployment = generate_tests_from_suite(
    test_suite, test_type="deployment"
)

# Usage:
#   pytest models/immunebuilder/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/immunebuilder/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/immunebuilder/test.py -n auto --no-cov -v -s                 # both
