from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.prody.config import MODEL_FAMILY

# TODO: ProDy Encode Test Non-Determinism Investigation
# ========================================================
#
# ISSUE ENCOUNTERED:
# When running encode tests multiple times with the same input (e.g., 1UBQ chain A),
# we observe slight variations in interaction counts, particularly for hydrogen bonds.
# For example:
#   - Run 1: 10 hydrogen bonds, 52 hydrophobic, 2 salt bridges
#   - Run 2: 11 hydrogen bonds, 52 hydrophobic, 2 salt bridges
#   - Run 3: 10 hydrogen bonds, 52 hydrophobic, 2 salt bridges
#
# ROOT CAUSE:
# The non-determinism stems from the hydrogen addition process (PDBFixer/OpenBabel):
# 1. Hydrogen atom placement has slight variations between runs due to:
#    - Non-deterministic optimization algorithms in PDBFixer
#    - Floating point precision in energy minimization
#    - Different initial random states
# 2. ProDy's interaction detection uses distance/angle cutoffs
# 3. Borderline interactions (right at the cutoff thresholds) may be detected
#    or missed depending on the exact hydrogen placement
#
# BIOLOGICAL IMPLICATIONS:
# - The core, stable interactions remain consistent (e.g., hydrophobic, salt bridges)
# - Only borderline hydrogen bonds near cutoff thresholds vary (typically ±1-2)
# - This is acceptable because:
#   a) These borderline interactions are weak/transient in reality
#   b) The overall interaction profile remains stable
#   c) This reflects real uncertainty in hydrogen placement for predicted structures
#
# SOLUTION IMPLEMENTED:
# We use a custom validator (`validate_encode_interaction_counts`) that checks:
# - Interaction counts by type (hydrogen bonds, hydrophobic, salt bridges, etc.)
# - Rather than exact atom-level matches
# - This allows for the ±1-2 variation in borderline interactions while ensuring
#   the overall interaction profile is consistent
#
# FUTURE IMPROVEMENTS:
# 1. Investigate if ProDy's hydrogen addition can be made deterministic by:
#    - Setting explicit random seeds for PDBFixer's energy minimization
#    - Using consistent pH and temperature parameters
#    - Pre-processing structures to ensure deterministic starting states
# 2. Consider implementing tolerance ranges for interaction counts (e.g., ±2)
# 3. Document expected interaction count ranges for common test structures
# 4. Add integration tests that verify interaction count stability over N runs
#
# RELATED: RMSD Near-Zero Values
# For RMSD tests comparing identical structures, we observe values like 1.16e-14
# instead of exactly 0.0. This is expected due to floating point precision limits
# in the alignment and RMSD calculation algorithms. These values are effectively
# zero for all practical purposes.


def _assert_interaction_counts(expected_counts: dict, actual_counts: dict, label: str):
    """Check interaction counts with ±1 tolerance for hydrogen bonds, exact for others."""
    for interaction_type, expected_count in expected_counts.items():
        assert (
            interaction_type in actual_counts
        ), f"{label}: missing interaction type '{interaction_type}'"

        actual_count = actual_counts[interaction_type]

        if interaction_type == "hydrogen_bond":
            # Allow ±1 for hydrogen bonds (due to borderline detection at cutoff thresholds)
            assert abs(actual_count - expected_count) <= 1, (
                f"{label}: hydrogen_bond count out of range. "
                f"Expected {expected_count} (±1), got {actual_count}"
            )
        else:
            # Require exact match for all other interaction types
            assert actual_count == expected_count, (
                f"{label}: {interaction_type} count mismatch. "
                f"Expected {expected_count}, got {actual_count}"
            )


def validate_encode_interaction_counts(actual: dict, expected: dict | None = None):
    """
    Custom validator for encode tests that checks interaction counts instead of exact matches.
    This is needed because ProDy+PDBFixer can produce non-deterministic results for exact atoms,
    but the overall interaction counts should be consistent.

    Allows ±1 variation for hydrogen bonds (due to borderline detection at cutoff thresholds),
    but requires exact matches for all other interaction types.
    """
    assert "results" in actual, "Actual output missing 'results' key"

    if expected is None:
        return

    assert "results" in expected, "Expected output missing 'results' key"

    for i, (actual_result, expected_result) in enumerate(
        zip(actual["results"], expected["results"], strict=False)
    ):
        # Check intra-chain interaction counts
        if "intra_chain_interactions" in expected_result:
            assert (
                "intra_chain_interactions" in actual_result
            ), f"Result {i}: missing intra_chain_interactions"

            for chain_id in expected_result["intra_chain_interactions"]:
                assert (
                    chain_id in actual_result["intra_chain_interactions"]
                ), f"Result {i}: missing chain {chain_id}"

                expected_chain = expected_result["intra_chain_interactions"][chain_id]
                actual_chain = actual_result["intra_chain_interactions"][chain_id]

                _assert_interaction_counts(
                    expected_chain["interaction_counts"],
                    actual_chain["interaction_counts"],
                    f"Result {i}, Chain {chain_id}",
                )

        # Check pair interaction counts with same tolerance
        if "pair_interactions" in expected_result:
            assert (
                "pair_interactions" in actual_result
            ), f"Result {i}: missing pair_interactions"

            for pair_key in expected_result["pair_interactions"]:
                assert (
                    pair_key in actual_result["pair_interactions"]
                ), f"Result {i}: missing pair {pair_key}"

                expected_pair = expected_result["pair_interactions"][pair_key]
                actual_pair = actual_result["pair_interactions"][pair_key]

                _assert_interaction_counts(
                    expected_pair["interaction_counts"],
                    actual_pair["interaction_counts"],
                    f"Result {i}, Pair {pair_key}",
                )


# ProDy test suite - single variant, multiple test cases
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single mapping for the single variant
        VariantTestMapping(
            variant_config={},  # Empty dict for single variant
            test_cases=[
                # Encode tests - use custom validator due to ProDy/PDBFixer non-determinism
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture="encode_single_chain_input_v2.json",
                    expected_output_fixture="encode_single_chain_expected_output_v2.json",
                    validator=validate_encode_interaction_counts,
                    remote_fn_kwargs={"_skip_cache": True},
                ),
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture="encode_multi_chain_input_v2.json",
                    expected_output_fixture="encode_multi_chain_expected_output_v2.json",
                    validator=validate_encode_interaction_counts,
                    remote_fn_kwargs={"_skip_cache": True},
                ),
                # Predict tests - use higher relative tolerance for floating point precision
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture="predict_single_chain_same_input.json",
                    expected_output_fixture="predict_single_chain_same_expected_output.json",
                    tolerances={"rel_tol": 2.0},  # Very relaxed for near-zero RMSDs
                    remote_fn_kwargs={"_skip_cache": True},
                ),
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture="predict_multi_chain_same_input.json",
                    expected_output_fixture="predict_multi_chain_same_expected_output.json",
                    tolerances={"rel_tol": 2.0},  # Very relaxed for near-zero RMSDs
                    remote_fn_kwargs={"_skip_cache": True},
                ),
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture="predict_different_lengths_input.json",
                    expected_output_fixture="predict_different_lengths_expected_output.json",
                    tolerances={
                        "rel_tol": 0.05
                    },  # 5% tolerance for different length RMSDs
                    remote_fn_kwargs={"_skip_cache": True},
                ),
            ],
        )
    ],
)

# Generate integration tests (marked with @pytest.mark.integration)
test_prody_integration = generate_tests_from_suite(test_suite, test_type="integration")

# Generate deployment tests (marked with @pytest.mark.deployment)
test_prody_deployment = generate_tests_from_suite(test_suite, test_type="deployment")

# Usage:
#   pytest models/prody/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/prody/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/prody/test.py -n auto --no-cov -v -s                 # both
