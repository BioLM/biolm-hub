"""
Integration tests for sequence diversity and reproducibility in the AntiFold generate() endpoint.

Validates that time-based seeding produces diverse outputs across multiple invocations
(even with Modal memory snapshots) and that an explicit seed yields reproducible results.
"""

import pytest

from models.antifold.app import app

# Test PDB: 10-residue structure for meaningful diversity testing
TEST_PDB_10_RESIDUES = """ATOM      1  N   MET A   1       0.000   0.000   0.000  1.00  0.00           N
ATOM      2  CA  MET A   1       1.458   0.000   0.000  1.00  0.00           C
ATOM      3  C   MET A   1       2.021   1.419   0.000  1.00  0.00           C
ATOM      4  O   MET A   1       1.256   2.382   0.000  1.00  0.00           O
ATOM      5  N   ALA A   2       3.350   1.560   0.000  1.00  0.00           N
ATOM      6  CA  ALA A   2       4.075   2.824   0.000  1.00  0.00           C
ATOM      7  C   ALA A   2       5.585   2.623   0.000  1.00  0.00           C
ATOM      8  O   ALA A   2       6.105   1.505   0.000  1.00  0.00           O
ATOM      9  N   VAL A   3       6.318   3.742   0.000  1.00  0.00           N
ATOM     10  CA  VAL A   3       7.782   3.742   0.000  1.00  0.00           C
ATOM     11  C   VAL A   3       8.345   5.161   0.000  1.00  0.00           C
ATOM     12  O   VAL A   3       7.580   6.124   0.000  1.00  0.00           O
ATOM     13  N   LEU A   4       9.674   5.302   0.000  1.00  0.00           N
ATOM     14  CA  LEU A   4      10.399   6.566   0.000  1.00  0.00           C
ATOM     15  C   LEU A   4      11.909   6.365   0.000  1.00  0.00           C
ATOM     16  O   LEU A   4      12.429   5.247   0.000  1.00  0.00           O
ATOM     17  N   ILE A   5      12.642   7.484   0.000  1.00  0.00           N
ATOM     18  CA  ILE A   5      14.106   7.484   0.000  1.00  0.00           C
ATOM     19  C   ILE A   5      14.669   8.903   0.000  1.00  0.00           C
ATOM     20  O   ILE A   5      13.904   9.866   0.000  1.00  0.00           O
ATOM     21  N   SER A   6      15.998   9.044   0.000  1.00  0.00           N
ATOM     22  CA  SER A   6      16.723  10.308   0.000  1.00  0.00           C
ATOM     23  C   SER A   6      18.233  10.107   0.000  1.00  0.00           C
ATOM     24  O   SER A   6      18.753   8.989   0.000  1.00  0.00           O
ATOM     25  N   THR A   7      18.966  11.226   0.000  1.00  0.00           N
ATOM     26  CA  THR A   7      20.430  11.226   0.000  1.00  0.00           C
ATOM     27  C   THR A   7      20.993  12.645   0.000  1.00  0.00           C
ATOM     28  O   THR A   7      20.228  13.608   0.000  1.00  0.00           O
ATOM     29  N   ASP A   8      22.322  12.786   0.000  1.00  0.00           N
ATOM     30  CA  ASP A   8      23.047  14.050   0.000  1.00  0.00           C
ATOM     31  C   ASP A   8      24.557  13.849   0.000  1.00  0.00           C
ATOM     32  O   ASP A   8      25.077  12.731   0.000  1.00  0.00           O
ATOM     33  N   GLY A   9      25.290  14.968   0.000  1.00  0.00           N
ATOM     34  CA  GLY A   9      26.754  14.968   0.000  1.00  0.00           C
ATOM     35  C   GLY A   9      27.317  16.387   0.000  1.00  0.00           C
ATOM     36  O   GLY A   9      26.552  17.350   0.000  1.00  0.00           O
ATOM     37  N   LYS A  10      28.646  16.528   0.000  1.00  0.00           N
ATOM     38  CA  LYS A  10      29.371  17.792   0.000  1.00  0.00           C
ATOM     39  C   LYS A  10      30.881  17.591   0.000  1.00  0.00           C
ATOM     40  O   LYS A  10      31.401  16.473   0.000  1.00  0.00           O
END
"""


def extract_sequences_from_response(response: dict) -> list[str]:
    """Extract all sequences from an AntiFold generate response."""
    sequences = []

    if "results" not in response:
        return sequences

    for result in response["results"]:
        if isinstance(result, dict) and "sequences" in result:
            for seq_item in result["sequences"]:
                if isinstance(seq_item, dict) and "heavy_chain" in seq_item:
                    sequences.append(seq_item["heavy_chain"])
                    if seq_item.get("light_chain"):
                        sequences.append(seq_item["light_chain"])

    return sequences


@pytest.mark.integration
@pytest.mark.parametrize(
    "temperature,num_calls,min_diversity_pct",
    [
        (0.5, 10, 50.0),  # Medium temp: expect ≥50% unique sequences
        (1.0, 10, 70.0),  # High temp: expect ≥70% unique sequences
    ],
)
def test_generate_diversity(
    temperature: float, num_calls: int, min_diversity_pct: float
):
    """
    Test that generate() produces diverse sequences across multiple calls.

    Validates that time-based seeding yields diverse outputs even across
    repeated calls with the same input (including Modal memory snapshots).
    """
    model_class = app.registered_classes.get("AntiFoldModel")
    assert model_class is not None, "AntiFoldModel not found in app"

    with app.run():
        model = model_class()

        payload = {
            "params": {
                "heavy_chain_id": "A",
                "num_seq_per_target": 4,
                "sampling_temp": temperature,
                "regions": ["all"],
            },
            "items": [{"pdb": TEST_PDB_10_RESIDUES}],
        }

        all_sequences = []
        for _ in range(num_calls):
            response = model.generate.remote(payload)
            sequences = extract_sequences_from_response(response)
            all_sequences.extend(sequences)

        assert len(all_sequences) > 0, "No sequences extracted from responses"

        unique_sequences = set(all_sequences)
        diversity_pct = (len(unique_sequences) / len(all_sequences)) * 100

        assert diversity_pct >= min_diversity_pct, (
            f"Diversity {diversity_pct:.1f}% is below threshold {min_diversity_pct}%. "
            f"Found {len(unique_sequences)} unique sequences out of {len(all_sequences)} total."
        )


@pytest.mark.integration
def test_generate_seed_reproducibility():
    """Test that explicit seed produces reproducible results."""
    model_class = app.registered_classes.get("AntiFoldModel")
    assert model_class is not None, "AntiFoldModel not found in app"

    with app.run():
        model = model_class()

        payload = {
            "params": {
                "heavy_chain_id": "A",
                "num_seq_per_target": 2,
                "sampling_temp": 0.5,
                "regions": ["all"],
                "seed": 42,
            },
            "items": [{"pdb": TEST_PDB_10_RESIDUES}],
        }

        sequences_1 = extract_sequences_from_response(model.generate.remote(payload))
        sequences_2 = extract_sequences_from_response(model.generate.remote(payload))
        sequences_3 = extract_sequences_from_response(model.generate.remote(payload))

        assert (
            sequences_1 == sequences_2
        ), "Seed=42 produced different results on call 2"
        assert (
            sequences_1 == sequences_3
        ), "Seed=42 produced different results on call 3"

        # Different seed should produce different results
        payload["params"]["seed"] = 123
        sequences_different = extract_sequences_from_response(
            model.generate.remote(payload)
        )
        assert (
            sequences_different != sequences_1
        ), "Different seeds produced identical results"


@pytest.mark.integration
def test_generate_default_is_diverse():
    """Test that generate() without seed produces diverse results."""
    model_class = app.registered_classes.get("AntiFoldModel")
    assert model_class is not None, "AntiFoldModel not found in app"

    with app.run():
        model = model_class()

        payload = {
            "params": {
                "heavy_chain_id": "A",
                "num_seq_per_target": 2,
                "sampling_temp": 1.0,
                "regions": ["all"],
            },
            "items": [{"pdb": TEST_PDB_10_RESIDUES}],
        }

        all_sequences = []
        for _ in range(5):
            response = model.generate.remote(payload)
            sequences = extract_sequences_from_response(response)
            all_sequences.extend(sequences)

        unique_sequences = set(all_sequences)
        assert len(unique_sequences) >= 5, (
            f"Expected at least 5 unique sequences at temp=1.0, "
            f"but got {len(unique_sequences)} out of {len(all_sequences)}."
        )
