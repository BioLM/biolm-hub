from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.dsm.config import MODEL_FAMILY
from models.dsm.fixture import (
    ENCODE_MEAN_INPUT,
    ENCODE_MEAN_OUTPUT_TPL,
    ENCODE_PER_RESIDUE_INPUT,
    ENCODE_PER_RESIDUE_OUTPUT_TPL,
    GENERATE_CONDITIONAL_INPUT,
    GENERATE_MASKED_INPUT,
    GENERATE_UNCONDITIONAL_INPUT,
    SCORE_INPUT,
    SCORE_OUTPUT_TPL,
)
from models.dsm.schema import DSMParams


def _validate_dsm_generate(actual_output: dict, _expected_output: dict | None = None):
    """Validator for DSM generation that checks structure and basic properties."""
    assert "results" in actual_output, "Response missing 'results' key"
    assert actual_output["results"], "Results list is empty"

    # Check that we have results for each input item
    for i, item_results in enumerate(actual_output["results"]):
        assert isinstance(item_results, list), f"Item {i} results should be a list"
        assert item_results, f"Item {i} has no generated sequences"

        for j, seq_result in enumerate(item_results):
            assert (
                "sequence" in seq_result
            ), f"Item {i}, sequence {j} missing 'sequence' key"
            assert (
                "log_prob" in seq_result
            ), f"Item {i}, sequence {j} missing 'log_prob' key"
            assert (
                "perplexity" in seq_result
            ), f"Item {i}, sequence {j} missing 'perplexity' key"

            sequence = seq_result["sequence"]
            assert isinstance(
                sequence, str
            ), f"Item {i}, sequence {j} sequence should be string"
            assert (
                len(sequence) > 0
            ), f"Item {i}, sequence {j} sequence should not be empty"
            assert (
                len(sequence) <= DSMParams.max_sequence_len
            ), f"Item {i}, sequence {j} sequence too long"

            # Check that sequence contains only valid amino acids (including ambiguous)
            # Standard 20 AAs: ACDEFGHIKLMNPQRSTVWY
            # Ambiguous AAs: X (unknown), B (Asn/Asp), Z (Gln/Glu), J (Leu/Ile), U (Selenocysteine), O (Pyrrolysine)
            valid_aas = set("ACDEFGHIKLMNPQRSTVWYXBZJUO")
            invalid_chars = set(sequence) - valid_aas
            assert (
                not invalid_chars
            ), f"Item {i}, sequence {j} contains invalid characters: {invalid_chars}"

            # Check optional second sequence for PPI models
            if "sequence2" in seq_result:
                seq2 = seq_result["sequence2"]
                # Treat empty strings as None (should be normalized in app code, but handle here too)
                if seq2 is not None and seq2 != "":
                    assert isinstance(
                        seq2, str
                    ), f"Item {i}, sequence {j} sequence2 should be string"
                    assert (
                        len(seq2) > 0
                    ), f"Item {i}, sequence {j} sequence2 should not be empty"
                    # Use same valid_aas set (defined above) for sequence2
                    invalid_chars_2 = set(seq2) - valid_aas
                    assert (
                        not invalid_chars_2
                    ), f"Item {i}, sequence {j} sequence2 contains invalid characters: {invalid_chars_2}"

            # Check log_prob and perplexity are reasonable
            log_prob = seq_result["log_prob"]
            perplexity = seq_result["perplexity"]
            assert isinstance(
                log_prob, int | float
            ), f"Item {i}, sequence {j} log_prob should be numeric"
            assert isinstance(
                perplexity, int | float
            ), f"Item {i}, sequence {j} perplexity should be numeric"
            assert (
                perplexity > 0
            ), f"Item {i}, sequence {j} perplexity should be positive"


# DSM test suite - multiple variants, multiple actions
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single mapping that applies to ALL variants
        VariantTestMapping(
            variant_config={},  # Empty dict means applies to ALL variants
            test_cases=[
                # Generate action - unconditional generation
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=GENERATE_UNCONDITIONAL_INPUT,
                    validator=_validate_dsm_generate,
                ),
                # Generate action - masked sequence generation
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=GENERATE_MASKED_INPUT,
                    validator=_validate_dsm_generate,
                ),
                # Generate action - conditional generation (sequence prefix)
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=GENERATE_CONDITIONAL_INPUT,
                    validator=_validate_dsm_generate,
                ),
                # Encode action - mean pooling
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=ENCODE_MEAN_INPUT,
                    expected_output_fixture=ENCODE_MEAN_OUTPUT_TPL,
                    tolerances={"rel_tol": 1e-4, "cosine_distance_threshold": 0.02},
                ),
                # Encode action - per-residue embeddings
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=ENCODE_PER_RESIDUE_INPUT,
                    expected_output_fixture=ENCODE_PER_RESIDUE_OUTPUT_TPL,
                    tolerances={"rel_tol": 1e-4, "cosine_distance_threshold": 0.02},
                ),
                # Score action - log probabilities
                ActionTestCase(
                    action_name=ModelActions.SCORE,
                    input_fixture=SCORE_INPUT,
                    expected_output_fixture=SCORE_OUTPUT_TPL,
                    tolerances={"rel_tol": 1e-4, "cosine_distance_threshold": 0.02},
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
#   pytest models/dsm/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/dsm/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/dsm/test.py -n auto --no-cov -v -s                 # both
