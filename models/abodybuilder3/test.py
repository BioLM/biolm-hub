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
test_abodybuilder3_integration = generate_tests_from_suite(
    test_suite, test_type="integration"
)

# Generate deployment tests (marked with @pytest.mark.deployment)
test_abodybuilder3_deployment = generate_tests_from_suite(
    test_suite, test_type="deployment"
)


def test_plddt_response_accepts_flat_list() -> None:
    """Regression (was a latent 500 on ``plddt=True``): the fold action emits a
    flat per-residue ``list[float]`` (``output['plddt'].squeeze(0).tolist()``),
    so the response field must accept that shape — not ``list[list[float]]``."""
    from models.abodybuilder3.schema import AbodyBuilder3PredictResponseResult

    result = AbodyBuilder3PredictResponseResult(pdb="FAKEPDB", plddt=[85.2, 92.1, 77.0])
    assert result.plddt == [85.2, 92.1, 77.0]


# Usage:
#   pytest models/abodybuilder3/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/abodybuilder3/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/abodybuilder3/test.py -n auto --no-cov -v -s                 # both
