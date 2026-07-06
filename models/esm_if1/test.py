from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.esm_if1.config import MODEL_FAMILY
from models.esm_if1.fixture import (
    GENERATE_INPUT,
    GENERATE_OUTPUT,
)

# ESM-IF1 test suite - single variant model with one action
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single mapping that applies to the single variant
        VariantTestMapping(
            variant_config={},  # Empty dict means applies to ALL variants (only one in this case)
            test_cases=[
                # is_generated_seq compares length only, NOT the residues — deliberate:
                # ESM-IF1 GENERATES sequences by temperature sampling from the inverse-
                # folding distribution, so the exact residues differ run to run and a
                # numeric golden comparison would be meaningless. The golden fixture pins
                # the expected sequence length (a stable structural property) instead.
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=GENERATE_INPUT,
                    expected_output_fixture=GENERATE_OUTPUT,
                    tolerances={
                        # The generated `sequence` is length-only compared
                        # (is_generated_seq) because temperature sampling changes
                        # the exact residues run to run. The only numeric field is
                        # `recovery` (native-match fraction, on [0, 1]). The old
                        # rel_tol=0.5 let it drift +/-50% (e.g. 0.5 -> 0.25 would
                        # pass), masking a real regression. Bound it instead to
                        # ~+/-0.1 absolute (about two residues for a ~46-residue
                        # test protein) / +/-10% relative — tight enough to catch a
                        # genuine drop, loose enough for run-to-run sampling jitter.
                        "rel_tol": 0.1,
                        "abs_tol": 0.1,
                        "is_generated_seq": True,
                    },
                ),
            ],
        )
    ],
)

# Generate integration tests (marked with @pytest.mark.integration)
test_esm_if1_integration = generate_tests_from_suite(
    test_suite, test_type="integration"
)

# Generate deployment tests (marked with @pytest.mark.deployment)
test_esm_if1_deployment = generate_tests_from_suite(test_suite, test_type="deployment")

# Usage:
#   pytest models/esm_if1/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/esm_if1/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/esm_if1/test.py -n auto --no-cov -v -s                 # both
