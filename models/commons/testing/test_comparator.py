from models.commons.testing.comparator import compare_outputs


def test_pdb_rmsds_are_close() -> None:
    # Positive case
    pdb1 = (
        "ATOM      1  N   MET A   1      57.182  31.812   3.287  1.00 17.07           N\n"
        "ATOM      2  CA  MET A   1      56.266  31.198   4.309  1.00 15.02           C"
    )
    pdb2 = (
        "ATOM      1  N   MET A   1      57.281  31.712   3.177  1.00 17.07           N\n"
        "ATOM      2  CA  MET A   1      56.466  31.398   4.409  1.00 15.02           C"
    )
    assert compare_outputs(
        {"pdb": pdb1}, {"pdb": pdb2}, pdb_rmsd_threshold=1.5
    ), "Computed RMSD is more than threshold"

    # Negative case
    pdb3 = (
        "ATOM      1  N   LYS A   1      51.182  36.212   6.287  1.00 11.07           N\n"
        "ATOM      2  CA  LYS A   1      52.166  35.898   5.109  1.00 13.12           C"
    )
    assert compare_outputs(
        {"pdb": pdb1}, {"pdb": pdb3}, pdb_rmsd_threshold=8
    ), "Computed RMSD is more than threshold"

    # Edge case
    pdb4 = (
        "ATOM      1  N   LEU A   1      54.982  33.412   2.177  1.00 19.17           N\n"
        "ATOM      2  CA  LEU A   1      53.966  34.198   3.109  1.00 17.22           C"
    )
    assert compare_outputs(
        {"pdb": pdb1}, {"pdb": pdb4}, pdb_rmsd_threshold=4.0
    ), "Computed RMSD is more than threshold"

    # Longer positive case
    pdb5 = (
        "ATOM      1  N   MET A   1      57.182  31.812   3.287  1.00 17.07           N\n"
        "ATOM      2  CA  MET A   1      56.266  31.198   4.309  1.00 15.02           C\n"
        "ATOM      3  CA  LYS A 100      51.224  32.195   2.176  1.00 11.23           C"
    )

    pdb6 = (
        "ATOM      1  N   MET A   1      57.281  31.712   3.177  1.00 17.07           N\n"
        "ATOM      2  CA  MET A   1      56.466  31.398   4.409  1.00 15.02           C\n"
        "ATOM      3  CA  LYS A 100      51.434  32.095   2.286  1.00 11.23           C"
    )
    assert compare_outputs(
        {"pdb": pdb5}, {"pdb": pdb6}, pdb_rmsd_threshold=1.5
    ), "Computed RMSD is more than threshold"

    # Structures with differing atom counts are now compared over the atoms they
    # share, keyed by (chain, residue, atom name) — mirroring the multi-entity
    # comparator — instead of being rejected outright. pdb7 has two extra atoms
    # (CA GLU A1, N VAL Z101) absent from pdb8; the three atoms they share
    # (N A1, CA Z100, CA Z200) superimpose to a low RMSD, so this now PASSES.
    pdb7 = (
        "ATOM      1  N   GLU A   1      17.183  53.112   2.287  1.00 17.07           N  \n"
        "ATOM      2  CA  GLU A   1      16.166  52.498   3.309  1.00 15.02           C  \n"
        "ATOM      3  CA  LYS Z 100      31.434  42.095   1.286  1.00 11.23           C  \n"
        "ATOM      4  N   VAL Z 101      29.183  41.012   2.177  1.00 19.17           N  \n"
        "ATOM      5  CA  TYR Z 200      21.224  32.195   2.176  1.00 11.23           C  "
    )

    pdb8 = (
        "ATOM      1  N   GLU A   1      17.383  53.212   2.177  1.00 17.07           N  \n"
        "ATOM      2  CA  LYS Z 100      31.524  42.195   1.386  1.00 11.23           C  \n"
        "ATOM      3  CA  TYR Z 200      21.434  32.295   2.286  1.00 11.23           C  "
    )
    assert compare_outputs(
        {"pdb": pdb7}, {"pdb": pdb8}, pdb_rmsd_threshold=1.5
    ), "Shared atoms superimpose within threshold — should pass on the intersection"


def test_pdb_rmsd_atom_reordering() -> None:
    """Atoms are paired by (chain, residue, atom name), not list order.

    The same three atoms serialised in a different order must still superimpose
    onto themselves at ~0 RMSD. Under the old positional pairing they were
    matched to the wrong partners and produced a large (~2.5 Å) RMSD.
    """
    pdb = (
        "ATOM      1  N   MET A   1      57.182  31.812   3.287  1.00 17.07           N\n"
        "ATOM      2  CA  MET A   1      56.266  31.198   4.309  1.00 15.02           C\n"
        "ATOM      3  CA  LYS A 100      51.224  32.195   2.176  1.00 11.23           C"
    )
    # Identical structure, atoms emitted in reverse serial order.
    pdb_reordered = (
        "ATOM      3  CA  LYS A 100      51.224  32.195   2.176  1.00 11.23           C\n"
        "ATOM      1  N   MET A   1      57.182  31.812   3.287  1.00 17.07           N\n"
        "ATOM      2  CA  MET A   1      56.266  31.198   4.309  1.00 15.02           C"
    )
    # A very tight threshold: only correct atom pairing yields ~0 RMSD.
    assert compare_outputs(
        {"pdb": pdb}, {"pdb": pdb_reordered}, pdb_rmsd_threshold=0.001
    ), "Re-ordered identical atoms should pair by identity and give ~0 RMSD"


def test_pdb_rmsd_disjoint_atoms_fail() -> None:
    """Structures sharing no (chain, residue, atom name) key cannot be compared."""
    pdb = (
        "ATOM      1  N   MET A   1      57.182  31.812   3.287  1.00 17.07           N\n"
        "ATOM      2  CA  MET A   1      56.266  31.198   4.309  1.00 15.02           C"
    )
    # Different chain and residue numbering → no shared atom identity.
    pdb_disjoint = (
        "ATOM      1  N   GLY B   5      57.182  31.812   3.287  1.00 17.07           N\n"
        "ATOM      2  CA  GLY B   5      56.266  31.198   4.309  1.00 15.02           C"
    )
    assert not compare_outputs(
        {"pdb": pdb}, {"pdb": pdb_disjoint}, pdb_rmsd_threshold=8.0
    ), "Structures with no shared atoms must not pass, even under a loose threshold"


def test_compare_outputs() -> None:
    # Test: Identical dictionaries
    dict1 = {"a": 1, "b": 2}
    dict2 = {"a": 1, "b": 2}
    assert compare_outputs(dict1, dict2, rel_tol=1e-5)

    # Test: Different keys
    dict3 = {"a": 1, "b": 2}
    dict4 = {"a": 1, "c": 2}
    assert not compare_outputs(dict3, dict4, rel_tol=1e-5)

    # Test: Different integer values
    dict5 = {"a": 1, "b": 2}
    dict6 = {"a": 2, "b": 2}
    assert not compare_outputs(dict5, dict6, rel_tol=1e-5)

    # Test: Different float values outside of tolerance
    dict7 = {"a": 1.0, "b": 2.0}
    dict8 = {"a": 1.1, "b": 2.0}
    assert not compare_outputs(dict7, dict8, rel_tol=1e-5)

    # Test: Different float values within tolerance
    dict9 = {"a": 1.00001, "b": 2.0}
    dict10 = {"a": 1.00002, "b": 2.0}
    assert compare_outputs(dict9, dict10, rel_tol=1e-5)

    # Test: Nested dictionaries
    dict11 = {"a": {"c": 1.00001, "d": 3}, "b": 2.0}
    dict12 = {"a": {"c": 1.00002, "d": 3}, "b": 2.0}
    assert compare_outputs(dict11, dict12, rel_tol=1e-5)

    # Test: Different values within nested dictionaries
    dict13 = {"a": {"c": 1.00001, "d": 3}, "b": 2.0}
    dict14 = {"a": {"c": 1.00002, "d": 4}, "b": 2.0}
    assert not compare_outputs(dict13, dict14, rel_tol=1e-5)

    # Test: Tolerance level
    dict15 = {"a": 1.0, "b": 2.0}
    dict16 = {"a": 1.0001, "b": 2.0}
    assert not compare_outputs(dict15, dict16, rel_tol=1e-5)
    assert compare_outputs(dict15, dict16, rel_tol=1e-3)

    # Test: Deeply nested dictionaries with close values
    dict17 = {"a": {"c": {"e": 1.00001, "f": {"g": 2.5}}}, "b": 2.0}
    dict18 = {"a": {"c": {"e": 1.00002, "f": {"g": 2.5}}}, "b": 2.0}
    assert compare_outputs(dict17, dict18, rel_tol=1e-5)

    # Test: Deeply nested dictionaries with values outside of tolerance
    dict19 = {"a": {"c": {"e": 1.00001, "f": {"g": 2.5}}}, "b": 2.0}
    dict20 = {"a": {"c": {"e": 1.00002, "f": {"g": 3.0}}}, "b": 2.0}
    # g's value is outside of tolerance
    assert not compare_outputs(dict19, dict20, rel_tol=1e-5)

    # Test: Deeply nested dictionaries with different keys
    dict21 = {"a": {"c": {"e": 1.00001, "f": {"g": 2.5}}}, "b": 2.0}
    dict22 = {"a": {"c": {"e": 1.00002, "f": {"h": 2.5}}}, "b": 2.0}
    # Different key 'h' here
    assert not compare_outputs(dict21, dict22, rel_tol=1e-5)


def test_cosine_vectors_within_threshold() -> None:
    # Two almost-parallel 3-D vectors → very small distance
    v1 = [1.0, 0.0, 0.0]
    v2 = [0.9999, 0.01, 0.0]
    # Two gates now apply once cosine passes: the cosine distance (~2.5e-5) and
    # the L2-norm magnitude ratio (~5e-5, since the vectors differ slightly in
    # length). Both are re-checked against rel_tol at the end, so rel_tol must be
    # at least as large as the larger of the two.
    assert compare_outputs(
        {"vec": v1}, {"vec": v2}, cosine_distance_threshold=0.01, rel_tol=1e-4
    )


def test_cosine_uniform_scale_fails() -> None:
    # A uniform rescale (all components ×2) is a genuine magnitude
    # regression that cosine alone is blind to (the vectors are parallel, so
    # cosine distance is exactly 0). The L2-norm magnitude gate must reject it.
    v_expected = [1.0, 2.0, 3.0]
    v_actual = [2.0, 4.0, 6.0]  # exactly 2× → norm ratio 2 → |2 - 1| = 1 > rel_tol
    assert not compare_outputs(
        {"vec": v_actual},
        {"vec": v_expected},
        cosine_distance_threshold=0.01,
        rel_tol=1e-4,
    ), "A uniform ×2 rescale must fail the magnitude gate even though cosine passes"

    # Same blind spot at matrix (2-D) granularity: every row scaled by the same
    # factor is parallel after flattening, so only the magnitude gate catches it.
    m_expected = [[1.0, 0.0], [0.0, 1.0]]
    m_actual = [[3.0, 0.0], [0.0, 3.0]]
    assert not compare_outputs(
        {"mat": m_actual},
        {"mat": m_expected},
        cosine_distance_threshold=0.01,
        rel_tol=1e-4,
    ), "A uniformly rescaled matrix must fail the magnitude gate"


def test_cosine_identical_vector_passes() -> None:
    # Identical vectors pass (cosine distance 0, norm ratio 1).
    v = [0.5, -1.5, 2.0, 0.0]
    assert compare_outputs(
        {"vec": list(v)}, {"vec": list(v)}, cosine_distance_threshold=0.0, rel_tol=1e-6
    )

    # A tiny perturbation that keeps both cosine distance and the norm ratio
    # within rel_tol still passes (deterministic goldens with ~equal norms).
    v_expected = [1.0, 2.0, 3.0]
    v_actual = [1.00001, 2.00002, 3.00001]
    assert compare_outputs(
        {"vec": v_actual},
        {"vec": v_expected},
        cosine_distance_threshold=0.01,
        rel_tol=1e-4,
    )


def test_cosine_same_magnitude_rotation_passes() -> None:
    # The existing cosine behavior is preserved — a small rotation
    # that keeps the L2 norm unchanged (unit → unit) still passes on the cosine
    # tolerance, and the magnitude gate does not spuriously reject it.
    v_expected = [1.0, 0.0, 0.0]
    # Unit vector rotated ~8° in-plane: cosine distance ≈ (1 - 0.99)/2 = 0.005,
    # comfortably inside the 0.01 threshold; ‖·‖ stays 1.0.
    v_actual = [0.99, (1.0 - 0.99**2) ** 0.5, 0.0]
    assert compare_outputs(
        {"vec": v_actual},
        {"vec": v_expected},
        cosine_distance_threshold=0.01,
        rel_tol=1e-6,
    ), "A same-magnitude rotation within the cosine tolerance must still pass"


def test_cosine_vectors_over_threshold() -> None:
    # Orthogonal vectors → distance 0.5, should fail when thr < 0.5
    v1 = [1.0, 0.0, 0.0]
    v2 = [0.0, 1.0, 0.0]
    assert not compare_outputs({"vec": v1}, {"vec": v2}, cosine_distance_threshold=0.1)


def test_cosine_matrix_rectangular_ragged_fallback() -> None:
    # First sub-list shorter → _flatten_list returns None → element-wise diff
    m1 = [[1, 0], [0, 1]]
    m2 = [[1, 0, 0], [0, 1, 0]]
    # Different shapes must be reported as mismatch
    assert not compare_outputs({"mat": m1}, {"mat": m2}, cosine_distance_threshold=0.01)


def test_cosine_3d_tensor_passes() -> None:
    # Two identical 2×2×2 tensors (flattenable to 1-D length-8)
    t1 = [[[1, 0], [0, 1]], [[1, 0], [0, 1]]]
    t2 = [[[1, 0], [0, 1]], [[1, 0], [0, 1]]]
    assert compare_outputs(
        {"tensor": t1}, {"tensor": t2}, cosine_distance_threshold=0.0
    )
