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

    # PDBs with different number of atoms should NOT pass comparison
    # (even with RMSD threshold, since we can't compute meaningful RMSD)
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
    # This should fail because structures have different atom counts
    assert not compare_outputs(
        {"pdb": pdb7}, {"pdb": pdb8}, pdb_rmsd_threshold=1.5
    ), "Structures with different atom counts should not pass comparison"


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
    # Note: cosine distance is ~2.5e-5, but final check uses rel_tol,
    # so we need to pass a rel_tol that's at least as large
    assert compare_outputs(
        {"vec": v1}, {"vec": v2}, cosine_distance_threshold=0.01, rel_tol=3e-5
    )


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
