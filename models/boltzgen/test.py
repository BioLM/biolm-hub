"""
BoltzGen integration, deployment, and slow tests.

Unit tests live in test_unit.py (schema validation, pipeline helpers).

Integration tests  (<5 min on warm GPU)
----------------------------------------
  generate-programmatic        — protein-small_molecule + ATP, num_designs=1,
                                 steps=["design"] only; validates CIF is produced

Slow tests  (30-60 min each, run manually before releases)
-----------------------------------------------------------
  chorismite (protein-small_molecule) — full 7-step pipeline, num_designs=3, budget=2
                                        validates CIF + sequence + metrics for all steps
  nanobody_7eow (nanobody-anything)   — full pipeline, 7eow CDR redesign, num_designs=3
                                        validates nanobody scaffold redesign end-to-end

Run
---
    pytest models/boltzgen/test_unit.py -v                           # unit tests
    pytest models/boltzgen/test.py -m integration --no-cov -v -s     # integration
    pytest models/boltzgen/test.py -m slow --no-cov -v -s            # slow
    pytest models/boltzgen/test.py -m deployment --no-cov -v -s      # deployment
"""

from typing import Any, Optional

from models.boltzgen.config import MODEL_FAMILY
from models.boltzgen.schema import (
    BoltzGenDesignParams,
    BoltzGenDesignRequest,
    BoltzGenDesignRequestItem,
    BoltzGenDesignResponse,
    BoltzGenEntity,
    BoltzGenLigandEntity,
    BoltzGenPipelineStep,
    BoltzGenProteinEntity,
    BoltzGenProtocol,
)
from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite

# Try to import gemmi for CIF validation (only available in Modal container)
try:
    import gemmi

    HAS_GEMMI = True
except ImportError:
    HAS_GEMMI = False


# ---------------------------------------------------------------------------
# Response validators
# ---------------------------------------------------------------------------


def validate_boltzgen_response(
    actual: Any, expected: Optional[dict[str, Any]] = None
) -> None:
    """Full-pipeline validator: requires CIF, sequence, AND metrics."""
    response = BoltzGenDesignResponse.model_validate(actual)
    assert response.results, "No results returned in response"

    for idx, result in enumerate(response.results):
        assert result.cif, f"Result {idx}: No CIF content"

        if HAS_GEMMI:
            try:
                cif_doc = gemmi.cif.read_string(result.cif)
                assert len(cif_doc) > 0, f"Result {idx}: CIF document is empty"
                block = cif_doc[0]
                structure = gemmi.make_structure_from_block(block)
                assert len(structure) > 0, f"Result {idx}: CIF has no models"
                assert len(structure[0]) > 0, f"Result {idx}: CIF has no chains"
            except Exception as e:
                raise AssertionError(f"Result {idx}: Invalid CIF format: {e}") from e
        else:
            assert result.cif.startswith(
                "data_"
            ), f"Result {idx}: CIF doesn't start with 'data_'"
            assert (
                "ATOM" in result.cif or "HETATM" in result.cif
            ), f"Result {idx}: CIF contains no atom records"

        assert result.sequence, f"Result {idx}: No sequence provided"
        valid_aa = set("ACDEFGHIKLMNPQRSTVWY")
        invalid = set(result.sequence) - valid_aa
        assert not invalid, f"Result {idx}: Invalid amino acids: {invalid}"

        assert result.metrics, f"Result {idx}: No metrics provided"
        assert len(result.metrics) > 0, f"Result {idx}: Metrics dict is empty"

    if len(response.results) > 1:
        sequences = [r.sequence for r in response.results if r.sequence]
        unique = set(sequences)
        assert len(unique) > 1, "All designs have identical sequences"
        min_unique = max(2, len(sequences) // 3)
        assert (
            len(unique) >= min_unique
        ), f"Only {len(unique)}/{len(sequences)} unique sequences"
        print(
            f"✅ Diversity: {len(unique)}/{len(sequences)} unique ({len(unique)/len(sequences):.1%})"
        )

    print(f"✅ Validated {len(response.results)} result(s)")


def validate_boltzgen_fast_response(
    actual: Any, expected: Optional[dict[str, Any]] = None
) -> None:
    """Fast-test validator: only requires CIF (no metrics, sequence optional).

    Used for design-only runs where analysis/filtering steps are skipped.
    """
    response = BoltzGenDesignResponse.model_validate(actual)

    assert response.results, "Response has no results"

    for idx, result in enumerate(response.results):
        assert result.cif, f"Result {idx}: No CIF content"
        if HAS_GEMMI:
            try:
                cif_doc = gemmi.cif.read_string(result.cif)
                assert len(cif_doc) > 0, f"Result {idx}: CIF is empty"
            except Exception as e:
                raise AssertionError(f"Result {idx}: Invalid CIF: {e}") from e
        else:
            assert (
                "ATOM" in result.cif or "HETATM" in result.cif or "data_" in result.cif
            )

    print(f"✅ Fast validate: {len(response.results)} CIF(s)")


# ---------------------------------------------------------------------------
# Fast integration test inputs (programmatic — no R2 fixture needed)
# ---------------------------------------------------------------------------

# Minimal protein-small_molecule request: 1 design, design step only.
# protein-small_molecule needs moldir (available in Modal container) but no CIF file.
# With num_designs=1 and steps=["design"], this runs a single diffusion sample — fast.
_FAST_INPUT = BoltzGenDesignRequest(
    items=[
        BoltzGenDesignRequestItem(
            entities=[
                BoltzGenEntity(
                    protein=BoltzGenProteinEntity(id="A", sequence="30..50")
                ),
                BoltzGenEntity(ligand=BoltzGenLigandEntity(id="B", ccd="ATP")),
            ]
        )
    ],
    params=BoltzGenDesignParams(
        protocol=BoltzGenProtocol.PROTEIN_SMALL_MOLECULE,
        num_designs=1,
        budget=1,
        diffusion_batch_size=1,
        steps=[BoltzGenPipelineStep.DESIGN],
    ),
)


# ---------------------------------------------------------------------------
# Integration / deployment test suite  (fast, <5 min on warm container)
# ---------------------------------------------------------------------------

test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={},
            test_cases=[
                # Structural validator (not a numeric golden comparison) is deliberate:
                # BoltzGen is a GENERATIVE diffusion designer — each run draws a fresh
                # diffusion sample, so the CIF coordinates, designed sequence, and metrics
                # differ run to run. There is no fixed "golden" to compare against; we
                # assert the output is a well-formed CIF instead.
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=_FAST_INPUT,
                    validator=validate_boltzgen_fast_response,
                ),
            ],
        ),
        # Full-pipeline tests live in slow_test_suite below (-m slow).
    ],
)

test_boltzgen_integration = generate_tests_from_suite(
    test_suite, test_type="integration"
)
test_boltzgen_deployment = generate_tests_from_suite(test_suite, test_type="deployment")


# ---------------------------------------------------------------------------
# Slow tests — full 7-step pipeline, minimal designs, run before releases
#
# These validate the complete design → inverse_folding → folding →
# [design_folding] → [affinity] → analysis → filtering pipeline end-to-end.
# Each test uses the minimum meaningful campaign size (num_designs=3, budget=2)
# and takes 30-60 min on a warm container.
#
# Run with:
#   pytest models/boltzgen/test.py -m slow -v --no-cov -s
# ---------------------------------------------------------------------------

slow_test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Full pipeline: protein-small_molecule (TSA ligand, ~140-180 AA binder)
        # All 7 steps: design → inv_fold → folding → design_folding → affinity → analysis → filtering
        # num_designs=3, budget=2 — matches the fixture generated by fixture.py
        VariantTestMapping(
            variant_config={},
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture="protein_small_molecule_chorismite_input.json",
                    validator=validate_boltzgen_response,
                ),
            ],
        ),
        # Full pipeline: nanobody-anything (7eow scaffold, CDR loop redesign)
        # Steps: design → inv_fold → folding → analysis → filtering (no design_folding/affinity)
        # num_designs=3, budget=2 — CIF embedded in R2 fixture
        VariantTestMapping(
            variant_config={},
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture="nanobody_7eow_simple_input.json",
                    validator=validate_boltzgen_response,
                ),
            ],
        ),
    ],
)

test_boltzgen_slow = generate_tests_from_suite(slow_test_suite, test_type="slow")


# Unit tests (schema validation, pipeline helpers) have been moved to
# test_unit.py for faster CI execution.
