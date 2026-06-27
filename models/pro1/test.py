from models.commons.data.validator import aa_unambiguous
from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.pro1.config import MODEL_FAMILY
from models.pro1.fixture import INPUT1, INPUT2, INPUT3
from models.pro1.schema import Pro1Variant


def _validate_pro1_generate(actual_output: dict, _expected_output: dict | None = None):
    """Structural validation for Pro-1 generate output.

    Pro-1 is stochastic — no golden output comparison. We check:
    - Response has 'results' list with at least one entry
    - Each result has 'reasoning' (non-empty string)
    - Each result has 'mutations' list (may be empty)
    - 'modified_sequence' is optional (may be None / missing — the platform
      serializer drops None-valued fields). If present, it must be a valid
      AA string.
    """
    valid_aa = set(aa_unambiguous)

    assert "results" in actual_output, "Response missing 'results' key"
    results = actual_output["results"]
    assert len(results) > 0, "Results list is empty — no iterations produced output"

    for i, result in enumerate(results):
        assert "reasoning" in result, f"Result {i} missing 'reasoning'"
        assert isinstance(
            result["reasoning"], str
        ), f"Result {i} 'reasoning' is not a string"
        assert len(result["reasoning"]) > 0, f"Result {i} 'reasoning' is empty"

        assert "mutations" in result, f"Result {i} missing 'mutations'"
        assert isinstance(
            result["mutations"], list
        ), f"Result {i} 'mutations' is not a list"

        seq = result.get("modified_sequence")
        if seq is not None:
            assert isinstance(
                seq, str
            ), f"Result {i} 'modified_sequence' is not a string"
            assert (
                len(seq) >= 10
            ), f"Result {i} 'modified_sequence' too short ({len(seq)} AA)"
            invalid = set(seq) - valid_aa
            assert (
                not invalid
            ), f"Result {i} 'modified_sequence' contains invalid AA: {invalid}"


# Pro-1 test suite — test both 8b and 8b-grpo variants.
# Stochastic outputs: no golden fixture comparison, structural validation only.
_test_cases = [
    # Input 1: FGF-1 fragment with biological context
    ActionTestCase(
        action_name=ModelActions.GENERATE,
        input_fixture=INPUT1,
        validator=_validate_pro1_generate,
    ),
    # Input 2: Carbonic anhydrase II with known mutations (iterative design)
    ActionTestCase(
        action_name=ModelActions.GENERATE,
        input_fixture=INPUT2,
        validator=_validate_pro1_generate,
    ),
    # Input 3: Minimal input (sequence only)
    ActionTestCase(
        action_name=ModelActions.GENERATE,
        input_fixture=INPUT3,
        validator=_validate_pro1_generate,
    ),
]

test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={"MODEL_VARIANT": Pro1Variant.SIZE_8B},
            test_cases=_test_cases,
        ),
        VariantTestMapping(
            variant_config={"MODEL_VARIANT": Pro1Variant.SIZE_8B_GRPO},
            test_cases=_test_cases,
        ),
    ],
)


# Generate integration tests (marked with @pytest.mark.integration)
test_pro1_integration = generate_tests_from_suite(test_suite, test_type="integration")

# Generate deployment tests (marked with @pytest.mark.deployment)
test_pro1_deployment = generate_tests_from_suite(test_suite, test_type="deployment")

# Usage:
#   pytest models/pro1/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/pro1/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/pro1/test.py -n auto --no-cov -v -s                 # both
