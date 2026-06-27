from models.commons.data.validator import aa_unambiguous
from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.zymctrl.config import MODEL_FAMILY
from models.zymctrl.fixture import ENCODE_INPUT, ENCODE_OUTPUT
from models.zymctrl.schema import (
    ZymCTRLGenerateParams,
    ZymCTRLGenerateRequest,
    ZymCTRLGenerateRequestItem,
)

# Use amino acid alphabet from commons for validation
AA_CHARS = set(aa_unambiguous)


def _validate_generate(
    actual_output: dict, _expected_output: dict | None = None
) -> None:
    """Validate generate endpoint output.

    Generate outputs are non-deterministic, so we validate structure and content
    rather than comparing to expected values.
    """
    assert "results" in actual_output, "Response missing 'results' key"
    assert actual_output["results"], "Results list is empty"

    # Check first result (we only send one item in test)
    samples = actual_output["results"][0]
    assert isinstance(samples, list), "Result should be a list of generated sequences"
    assert len(samples) > 0, "Should have at least one generated sequence"

    for sample in samples:
        # Check sequence is valid amino acids
        sequence = sample["sequence"]
        assert isinstance(sequence, str), "Sequence should be a string"
        assert len(sequence) > 0, "Sequence should not be empty"
        # Validate that sequence is mostly valid amino acids (allow some edge cases)
        aa_count = sum(1 for c in sequence if c in AA_CHARS)
        aa_ratio = aa_count / len(sequence) if sequence else 0
        assert (
            aa_ratio >= 0.8
        ), f"Sequence should be mostly valid amino acids, got {aa_ratio:.1%}"

        # Check perplexity is a valid float
        perplexity = sample["perplexity"]
        assert isinstance(perplexity, int | float), "Perplexity should be numeric"
        assert perplexity > 0, "Perplexity should be positive"


def _validate_encode(actual_output: dict, _expected_output: dict | None = None) -> None:
    """Validate encode endpoint output."""
    assert "results" in actual_output, "Response missing 'results' key"
    assert actual_output["results"], "Results list is empty"

    # ZymCTRL has 1280-dimensional embeddings
    expected_dim = 1280

    for result in actual_output["results"]:
        assert "sequence_index" in result, "Result missing 'sequence_index'"

        # Check embedding or per_token_embeddings
        has_embedding = "embedding" in result and result["embedding"] is not None
        has_per_token = (
            "per_token_embeddings" in result
            and result["per_token_embeddings"] is not None
        )

        assert (
            has_embedding or has_per_token
        ), "Result must have either 'embedding' or 'per_token_embeddings'"

        if has_embedding:
            embedding = result["embedding"]
            assert isinstance(embedding, list), "Embedding should be a list"
            assert (
                len(embedding) == expected_dim
            ), f"Embedding dimension should be {expected_dim}, got {len(embedding)}"
            assert all(
                isinstance(x, int | float) for x in embedding
            ), "Embedding values should be numeric"

        if has_per_token:
            per_token = result["per_token_embeddings"]
            assert isinstance(per_token, list), "Per-token embeddings should be a list"
            assert len(per_token) > 0, "Per-token embeddings should not be empty"
            for token_emb in per_token:
                assert (
                    len(token_emb) == expected_dim
                ), f"Token embedding dimension should be {expected_dim}"


# ZymCTRL test suite - single variant with generate and encode actions
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={},  # Single variant, applies to all
            test_cases=[
                # Generate action - use programmatic input with validator
                # (outputs are non-deterministic, so we validate structure only)
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=ZymCTRLGenerateRequest(
                        params=ZymCTRLGenerateParams(
                            temperature=0.8,
                            top_k=9,
                            repetition_penalty=1.2,
                            num_samples=2,
                            max_length=100,
                        ),
                        items=[
                            ZymCTRLGenerateRequestItem(ec_number="3.5.5.1"),
                        ],
                    ),
                    validator=_validate_generate,
                ),
                # Encode action - use file-based input with validator
                # (embeddings should be deterministic but we use validator for flexibility)
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=ENCODE_INPUT,
                    expected_output_fixture=ENCODE_OUTPUT,
                    validator=_validate_encode,
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
#   pytest models/zymctrl/test.py -m integration -n auto --no-cov -v -s
#   pytest models/zymctrl/test.py -m deployment -n auto --no-cov -v -s
#   pytest models/zymctrl/test.py -n auto --no-cov -v -s
