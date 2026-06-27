from models.commons.model.schema import ModelActions
from models.commons.storage.r2 import read_json_from_r2
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.commons.util.config import (
    r2_bucket_name,
    r2_test_data_dir,
)
from models.prostt5.config import MODEL_FAMILY
from models.prostt5.fixture import (
    AA_ENCODE_OUTPUT,
    AA_GENERATE_INPUT,
    AA_INPUT,
    FOLD_ENCODE_OUTPUT,
    FOLD_INPUT,
)
from models.prostt5.schema import (
    ProstT5EncodeRequestAA,
    ProstT5EncodeRequestFold,
    ProstT5GenerateRequestAA,
    ProstT5GenerateRequestFold,
    ProstT5Params,
)


def _validate_prostt5_generate(actual_output: dict, _expected_output=None):
    """Validate generate output using the request that produced it."""
    assert "results" in actual_output and actual_output["results"], "Missing results"

    sample_seq = actual_output["results"][0][0]["sequence"]
    is_aa = sample_seq.islower()

    req_file = "aa_generate_input.json" if is_aa else "fold_input.json"
    req_path = f"{r2_test_data_dir}/models/{ProstT5Params.base_model_slug}/{req_file}"
    request_json = read_json_from_r2(r2_bucket_name, req_path)

    request = (
        ProstT5GenerateRequestAA.model_validate(request_json)
        if is_aa
        else ProstT5GenerateRequestFold.model_validate(request_json)
    )

    samples = actual_output["results"][0]
    assert len(samples) == request.params.num_samples, "Wrong number of samples"

    for s in samples:
        seq = s["sequence"]
        if is_aa:
            assert seq.islower(), "AA sequences should be lowercase"
        else:
            assert seq.isupper(), "FOLD sequences should be uppercase"
        assert len(seq) == len(request.items[0].sequence), "Length mismatch"


# ProstT5 test suite - variant-specific test mappings based on direction and action
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Encode action for fold2AA direction - uses FOLD input (lowercase structural sequences)
        VariantTestMapping(
            variant_config={"MODEL_ACTION": "encode", "MODEL_DIRECTION": "fold2AA"},
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=FOLD_INPUT,  # fold_input.json contains lowercase structural sequences
                    request_schema=ProstT5EncodeRequestFold,  # Override: needs Fold schema for lowercase sequences
                    expected_output_fixture=FOLD_ENCODE_OUTPUT,
                    tolerances={"rel_tol": 1e-3, "cosine_distance_threshold": 0.02},
                ),
            ],
        ),
        # Encode action for AA2fold direction
        VariantTestMapping(
            variant_config={"MODEL_ACTION": "encode", "MODEL_DIRECTION": "AA2fold"},
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=AA_INPUT,  # aa_input.json contains uppercase amino acid sequences
                    request_schema=ProstT5EncodeRequestAA,  # Uses AA schema for uppercase sequences (matches config default)
                    expected_output_fixture=AA_ENCODE_OUTPUT,
                    tolerances={"rel_tol": 1e-3, "cosine_distance_threshold": 0.02},
                ),
            ],
        ),
        # Generate action for fold2AA direction
        VariantTestMapping(
            variant_config={"MODEL_ACTION": "generate", "MODEL_DIRECTION": "fold2AA"},
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=FOLD_INPUT,  # fold_input.json contains lowercase structural sequences
                    request_schema=ProstT5GenerateRequestFold,  # Override: needs Fold schema for lowercase sequences
                    # No expected output for generate - uses custom validator
                    validator=lambda actual, _=None: _validate_prostt5_generate(actual),
                ),
            ],
        ),
        # Generate action for AA2fold direction
        VariantTestMapping(
            variant_config={"MODEL_ACTION": "generate", "MODEL_DIRECTION": "AA2fold"},
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=AA_GENERATE_INPUT,  # aa_generate_input.json contains uppercase amino acid sequences
                    request_schema=ProstT5GenerateRequestAA,  # Uses AA schema for uppercase sequences (matches config default)
                    # No expected output for generate - uses custom validator
                    validator=lambda actual, _=None: _validate_prostt5_generate(actual),
                ),
            ],
        ),
    ],
)


# Generate integration tests (marked with @pytest.mark.integration)
generate_tests_from_suite(test_suite, test_type="integration")

# Generate deployment tests (marked with @pytest.mark.deployment)
generate_tests_from_suite(test_suite, test_type="deployment")

# Usage:
#   pytest models/prostt5/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/prostt5/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/prostt5/test.py -n auto --no-cov -v -s                 # both
