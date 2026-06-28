"""Unit tests for the shared test-asset library and its R2 path resolution.

Modal-free: exercises pure string logic only (no R2, no deploy).
"""

from models.commons.testing.runner import _fixture_r2_path
from models.commons.testing.shared_assets import (
    STANDARD_PROTEIN,
    STANDARD_PROTEIN_STABILITY,
)

_AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWY")


class TestSharedAssets:
    def test_standard_protein_is_a_valid_sequence(self):
        assert STANDARD_PROTEIN
        assert set(STANDARD_PROTEIN) <= _AMINO_ACIDS

    def test_stability_protein_is_a_valid_sequence(self):
        assert STANDARD_PROTEIN_STABILITY
        assert set(STANDARD_PROTEIN_STABILITY) <= _AMINO_ACIDS

    def test_assets_are_distinct(self):
        assert STANDARD_PROTEIN != STANDARD_PROTEIN_STABILITY


class TestFixtureR2Path:
    def test_per_model_path(self):
        assert (
            _fixture_r2_path("models", "esm2", "encode_input.json")
            == "test-data/models/esm2/encode_input.json"
        )

    def test_shared_path_bypasses_the_per_model_prefix(self):
        assert (
            _fixture_r2_path("models", "esm2", "shared/protein/standard.fasta")
            == "test-data/shared/protein/standard.fasta"
        )

    def test_shared_path_is_slug_independent(self):
        # A shared asset resolves to the same key regardless of the calling model.
        a = _fixture_r2_path("models", "esm2", "shared/pdb/example.cif")
        b = _fixture_r2_path("finetune", "temberture", "shared/pdb/example.cif")
        assert a == b == "test-data/shared/pdb/example.cif"
