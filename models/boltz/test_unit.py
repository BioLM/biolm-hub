"""
Pure unit tests for Boltz utility functions — no Modal, no GPU, no R2.

Tests mathematical correctness and edge cases of:
- pTM score kernel (ptm_func)
- d0 normalization parameter (calc_d0, calc_d0_array)
- Chain type classification (classify_chain_type)
- ipSAE metric computation (calculate_ipsae)
- ipAE metric computation (calculate_ipae)
- mmCIF parsing (parse_structure_from_cif)

Reference: Dunbrack 2025 "Res ipSAE loquunt" (PMC11844409).
"""

import numpy as np
import pytest

from models.boltz.utils import (
    calc_d0,
    calc_d0_array,
    calculate_ipae,
    calculate_ipsae,
    classify_chain_type,
    parse_structure_from_cif,
    ptm_func,
)


class TestPtmFunc:
    """Tests for the TM-score kernel: 1/(1 + (x/d0)^2)."""

    def test_perfect_alignment(self):
        """PAE=0 should give score=1.0."""
        assert ptm_func(np.array([0.0]), 5.0)[0] == pytest.approx(1.0)

    def test_at_d0(self):
        """When PAE=d0, score should be exactly 0.5."""
        assert ptm_func(np.array([5.0]), 5.0)[0] == pytest.approx(0.5)

    def test_large_pae(self):
        """Large PAE should give score near 0."""
        result = ptm_func(np.array([100.0]), 5.0)[0]
        assert result < 0.01

    def test_vectorized(self):
        """Should work on arrays."""
        x = np.array([0.0, 5.0, 100.0])
        result = ptm_func(x, 5.0)
        assert result.shape == (3,)
        assert result[0] == pytest.approx(1.0)
        assert result[1] == pytest.approx(0.5)


class TestCalcD0:
    """Tests for the d0 normalization parameter."""

    def test_formula_matches_yang_skolnick(self):
        """d0 = 1.24*(L-15)^(1/3) - 1.8 for L > 27."""
        L = 100.0
        expected = 1.24 * (L - 15) ** (1.0 / 3.0) - 1.8
        assert calc_d0(L) == pytest.approx(expected)

    def test_small_protein_clamped(self):
        """L < 27 should be clamped, d0 >= 1.0 for protein."""
        assert calc_d0(10) >= 1.0

    def test_nucleic_acid_minimum(self):
        """Nucleic acid pairs should have d0 >= 2.0."""
        assert calc_d0(10, pair_type="nucleic_acid") >= 2.0
        assert calc_d0(30, pair_type="nucleic_acid") >= 2.0

    def test_monotonically_increasing(self):
        """d0 should increase with chain length."""
        assert calc_d0(50) < calc_d0(100) < calc_d0(500)

    def test_array_version_matches_scalar(self):
        """calc_d0_array should match calc_d0 for each element."""
        lengths = np.array([10, 50, 100, 500])
        d0_array = calc_d0_array(lengths)
        for i, L in enumerate(lengths):
            assert d0_array[i] == pytest.approx(calc_d0(float(L)))


class TestClassifyChainType:
    """Tests for chain type classification (protein vs nucleic_acid)."""

    def test_protein_chains(self):
        chain_ids = np.array(["A", "A", "B", "B"])
        residues = np.array(["ALA", "GLY", "LEU", "VAL"])
        result = classify_chain_type(chain_ids, residues)
        assert result["A"] == "protein"
        assert result["B"] == "protein"

    def test_nucleic_acid_chains(self):
        chain_ids = np.array(["A", "A", "B", "B"])
        residues = np.array(["DA", "DC", "ALA", "GLY"])
        result = classify_chain_type(chain_ids, residues)
        assert result["A"] == "nucleic_acid"
        assert result["B"] == "protein"

    def test_rna_classified(self):
        chain_ids = np.array(["C", "C"])
        residues = np.array(["A", "U"])
        result = classify_chain_type(chain_ids, residues)
        assert result["C"] == "nucleic_acid"


class TestCalculateIpsae:
    """Tests for the core ipSAE calculation."""

    def _make_two_chain_data(self, n1=10, n2=10, pae_value=5.0):
        """Create synthetic two-chain data with uniform PAE."""
        n = n1 + n2
        pae_matrix = np.full((n, n), pae_value)
        chain_ids = ["A"] * n1 + ["B"] * n2
        residue_types = ["ALA"] * n1 + ["GLY"] * n2
        return pae_matrix, chain_ids, residue_types

    def test_basic_output_structure(self):
        """Should return nested dict with correct chain pairs."""
        pae, chains, restypes = self._make_two_chain_data()
        result = calculate_ipsae(pae, chains, restypes)

        assert "A" in result
        assert "B" in result
        assert "B" in result["A"]
        assert "A" in result["B"]
        # Should not have self-pairs
        assert "A" not in result["A"]
        assert "B" not in result["B"]

    def test_expected_metric_keys(self):
        """Each chain pair should have all 6 ipSAE metrics."""
        pae, chains, restypes = self._make_two_chain_data()
        result = calculate_ipsae(pae, chains, restypes)

        expected_keys = {
            "ipsae_min",
            "ipsae_max",
            "ipsae_avg",
            "ipsae_d0chn",
            "ipsae_d0dom",
            "ipsae_d0res",
        }
        assert set(result["A"]["B"].keys()) == expected_keys

    def test_values_in_zero_one_range(self):
        """All ipSAE metrics should be in [0, 1]."""
        pae, chains, restypes = self._make_two_chain_data(pae_value=3.0)
        result = calculate_ipsae(pae, chains, restypes)

        for chain1 in result:
            for chain2 in result[chain1]:
                for metric, value in result[chain1][chain2].items():
                    assert 0.0 <= value <= 1.0, f"{metric}={value} out of range"

    def test_min_leq_avg_leq_max(self):
        """Ordering: min <= avg <= max for d0res aggregations."""
        pae, chains, restypes = self._make_two_chain_data(pae_value=3.0)
        result = calculate_ipsae(pae, chains, restypes)

        metrics = result["A"]["B"]
        assert metrics["ipsae_min"] <= metrics["ipsae_avg"]
        assert metrics["ipsae_avg"] <= metrics["ipsae_max"]

    def test_low_pae_gives_high_scores(self):
        """Low PAE values should produce high ipSAE scores."""
        pae, chains, restypes = self._make_two_chain_data(pae_value=1.0)
        result = calculate_ipsae(pae, chains, restypes)
        assert result["A"]["B"]["ipsae_avg"] > 0.5

    def test_high_pae_filtered_out(self):
        """PAE above cutoff should be filtered, giving zero scores."""
        pae, chains, restypes = self._make_two_chain_data(pae_value=15.0)
        result = calculate_ipsae(pae, chains, restypes, pae_cutoff=10.0)

        metrics = result["A"]["B"]
        assert metrics["ipsae_avg"] == 0.0
        assert metrics["ipsae_min"] == 0.0
        assert metrics["ipsae_max"] == 0.0

    def test_empty_chains(self):
        """Should handle empty chains gracefully."""
        pae_matrix = np.full((5, 5), 3.0)
        chain_ids = ["A"] * 5  # Only one chain
        residue_types = ["ALA"] * 5
        result = calculate_ipsae(pae_matrix, chain_ids, residue_types)

        # Single chain - no inter-chain pairs
        assert result["A"] == {}

    def test_three_chains(self):
        """Should compute pairwise metrics for all chain pairs."""
        n = 30
        pae = np.full((n, n), 4.0)
        chains = ["A"] * 10 + ["B"] * 10 + ["C"] * 10
        restypes = ["ALA"] * 10 + ["GLY"] * 10 + ["LEU"] * 10
        result = calculate_ipsae(pae, chains, restypes)

        assert "B" in result["A"] and "C" in result["A"]
        assert "A" in result["B"] and "C" in result["B"]
        assert "A" in result["C"] and "B" in result["C"]

    def test_nucleic_acid_pair_type(self):
        """Nucleic acid chains should use d0 >= 2.0."""
        n = 20
        pae = np.full((n, n), 3.0)
        chains = ["A"] * 10 + ["B"] * 10
        restypes = ["ALA"] * 10 + ["DA"] * 10  # Chain B is DNA
        result = calculate_ipsae(pae, chains, restypes)

        # Should still produce valid results
        assert result["A"]["B"]["ipsae_avg"] > 0.0


class TestCalculateIpae:
    """Tests for the symmetrized mean PAE calculation."""

    def test_basic_structure(self):
        """Should return nested dict with correct chain pairs."""
        n = 20
        pae = np.full((n, n), 5.0)
        chains = ["A"] * 10 + ["B"] * 10
        result = calculate_ipae(pae, chains)

        assert "A" in result and "B" in result
        assert "B" in result["A"] and "A" in result["B"]

    def test_symmetric_pae_gives_symmetric_ipae(self):
        """Symmetric PAE matrix should give equal ipae(A,B) and ipae(B,A)."""
        n = 20
        pae = np.full((n, n), 5.0)
        chains = ["A"] * 10 + ["B"] * 10
        result = calculate_ipae(pae, chains)

        assert result["A"]["B"] == pytest.approx(result["B"]["A"])

    def test_uniform_pae_value(self):
        """Uniform PAE of X should give ipae=X for all pairs."""
        n = 20
        pae = np.full((n, n), 7.5)
        chains = ["A"] * 10 + ["B"] * 10
        result = calculate_ipae(pae, chains)

        assert result["A"]["B"] == pytest.approx(7.5)

    def test_single_chain_empty(self):
        """Single chain should produce empty inner dicts."""
        pae = np.full((5, 5), 3.0)
        chains = ["A"] * 5
        result = calculate_ipae(pae, chains)
        assert result["A"] == {}


class TestParseStructureFromCif:
    """Tests for mmCIF parsing."""

    @pytest.fixture
    def sample_cif(self):
        """Minimal mmCIF content with two chains."""
        return """data_test
loop_
_atom_site.group_PDB
_atom_site.id
_atom_site.type_symbol
_atom_site.label_atom_id
_atom_site.label_comp_id
_atom_site.label_asym_id
_atom_site.label_seq_id
_atom_site.Cartn_x
_atom_site.Cartn_y
_atom_site.Cartn_z
ATOM 1 C CA ALA A 1 1.0 2.0 3.0
ATOM 2 C CA GLY A 2 4.0 5.0 6.0
ATOM 3 C CA LEU B 1 7.0 8.0 9.0
"""

    def test_parses_chain_ids(self, sample_cif):
        chain_ids, coords, residue_types = parse_structure_from_cif(sample_cif)
        assert chain_ids == ["A", "A", "B"]

    def test_parses_coordinates(self, sample_cif):
        chain_ids, coords, residue_types = parse_structure_from_cif(sample_cif)
        assert coords.shape == (3, 3)
        np.testing.assert_array_almost_equal(coords[0], [1.0, 2.0, 3.0])

    def test_parses_residue_types(self, sample_cif):
        chain_ids, coords, residue_types = parse_structure_from_cif(sample_cif)
        assert residue_types == ["ALA", "GLY", "LEU"]

    def test_skips_non_ca_atoms(self):
        cif = """data_test
loop_
_atom_site.group_PDB
_atom_site.id
_atom_site.type_symbol
_atom_site.label_atom_id
_atom_site.label_comp_id
_atom_site.label_asym_id
_atom_site.label_seq_id
_atom_site.Cartn_x
_atom_site.Cartn_y
_atom_site.Cartn_z
ATOM 1 C CA ALA A 1 1.0 2.0 3.0
ATOM 2 N N ALA A 1 1.1 2.1 3.1
ATOM 3 C CB ALA A 1 1.2 2.2 3.2
"""
        chain_ids, coords, residue_types = parse_structure_from_cif(cif)
        assert len(chain_ids) == 1  # Only CA atom
        assert chain_ids[0] == "A"

    def test_skips_ligands(self):
        """Ligands have residue_seq_id == '.' and should be skipped."""
        cif = """data_test
loop_
_atom_site.group_PDB
_atom_site.id
_atom_site.type_symbol
_atom_site.label_atom_id
_atom_site.label_comp_id
_atom_site.label_asym_id
_atom_site.label_seq_id
_atom_site.Cartn_x
_atom_site.Cartn_y
_atom_site.Cartn_z
ATOM 1 C CA ALA A 1 1.0 2.0 3.0
HETATM 2 C CA LIG B . 4.0 5.0 6.0
"""
        chain_ids, coords, residue_types = parse_structure_from_cif(cif)
        assert len(chain_ids) == 1

    def test_empty_content(self):
        chain_ids, coords, residue_types = parse_structure_from_cif("")
        assert chain_ids == []
        assert coords.shape == (0, 3)
        assert residue_types == []

    def test_nucleic_acid_c1_atom(self):
        """C1' atoms from nucleic acids should be included."""
        cif = """data_test
loop_
_atom_site.group_PDB
_atom_site.id
_atom_site.type_symbol
_atom_site.label_atom_id
_atom_site.label_comp_id
_atom_site.label_asym_id
_atom_site.label_seq_id
_atom_site.Cartn_x
_atom_site.Cartn_y
_atom_site.Cartn_z
ATOM 1 C CA ALA A 1 1.0 2.0 3.0
ATOM 2 C C1' DA B 1 4.0 5.0 6.0
"""
        chain_ids, coords, residue_types = parse_structure_from_cif(cif)
        assert len(chain_ids) == 2
        assert chain_ids[1] == "B"
        assert residue_types[1] == "DA"
