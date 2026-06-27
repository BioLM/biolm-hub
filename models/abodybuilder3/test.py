from models.abodybuilder3.config import MODEL_FAMILY
from models.abodybuilder3.fixture import PREDICT_INPUT, PREDICT_OUTPUT_TPL
from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite

test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={},  # Applies to all variants
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=PREDICT_INPUT,
                    expected_output_fixture=PREDICT_OUTPUT_TPL,
                    tolerances={
                        "rel_tol": 1e-3,
                        "cosine_distance_threshold": 0.02,
                        "pdb_rmsd_threshold": 0.05,
                    },
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
#   pytest models/abodybuilder3/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/abodybuilder3/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/abodybuilder3/test.py -n auto --no-cov -v -s                 # both
