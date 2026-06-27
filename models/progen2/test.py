from models.commons.model.schema import ModelActions
from models.commons.storage.r2 import read_json_from_r2
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.commons.util.config import (
    r2_bucket_name,
    r2_test_data_dir,
)
from models.progen2.config import MODEL_FAMILY
from models.progen2.fixture import GENERATE_INPUT
from models.progen2.schema import ProGen2GenerateRequest, ProGen2Params


def _validate_progen2_generate(
    actual_output: dict, _expected_output: dict | None = None
):
    """Validator that mirrors the checks in the legacy standalone test."""
    # Load the same request payload that was sent to the model
    req_path = f"{r2_test_data_dir}/models/{ProGen2Params.base_model_slug}/input.json"
    req_data = read_json_from_r2(r2_bucket_name, req_path)
    request = ProGen2GenerateRequest.model_validate(req_data)

    assert "results" in actual_output, "Response missing 'results' key"
    assert actual_output["results"], "Results list is empty"

    samples = actual_output["results"][0]
    expected_count = request.params.num_samples
    context_prefix = request.items[0].context
    max_len = request.params.max_length

    assert len(samples) == expected_count, "Incorrect number of returned samples"

    for sample in samples:
        seq = sample["sequence"]
        assert seq.startswith(context_prefix), "Sample does not start with context"
        assert len(seq) <= max_len, "Sample exceeds max sequence length"


# ProGen2 test suite - all variants use the same input, validator checks output
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single mapping that applies to ALL variants
        VariantTestMapping(
            variant_config={},  # Empty dict means applies to ALL variants
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=GENERATE_INPUT,
                    # Use custom validator - no expected output file
                    validator=_validate_progen2_generate,
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
#   pytest models/progen2/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/progen2/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/progen2/test.py -n auto --no-cov -v -s                 # both
