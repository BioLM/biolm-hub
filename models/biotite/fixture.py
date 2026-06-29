from models.biotite.config import MODEL_FAMILY
from models.biotite.schema import (
    BiotiteExtractChainsRequest,
    BiotiteExtractChainsRequestItem,
    BiotiteRMSDRequest,
    BiotiteRMSDRequestItem,
)
from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator

# Fixture filename constants
GENERATE_INPUT = "generate_input.json"
GENERATE_OUTPUT = "generate_expected_output.json"
PREDICT_INPUT = "predict_input.json"
PREDICT_OUTPUT = "predict_expected_output.json"

# Sample PDB structures for testing
# ruff: noqa: W291 - PDB format requires trailing whitespace on ATOM lines
_SAMPLE_PDB_MULTI_CHAIN = """ATOM      1  N   ALA A   1      27.462  14.144   5.469  1.00 20.00           N
ATOM      2  CA  ALA A   1      26.132  14.439   6.109  1.00 20.00           C
ATOM      3  C   ALA A   1      25.170  13.249   6.109  1.00 20.00           C
ATOM      4  O   ALA A   1      25.170  12.249   6.109  1.00 20.00           O
ATOM      5  CB  ALA A   1      26.132  14.439   7.609  1.00 20.00           C
ATOM      6  N   GLY B   1      30.000  15.000   8.000  1.00 20.00           N
ATOM      7  CA  GLY B   1      31.000  16.000   9.000  1.00 20.00           C
ATOM      8  C   GLY B   1      32.000  17.000  10.000  1.00 20.00           C
ATOM      9  O   GLY B   1      33.000  18.000  11.000  1.00 20.00           O
TER      10      ALA A   1
TER      11      GLY B   1
END"""

_SAMPLE_PDB_SINGLE_CHAIN = """ATOM      1  N   ALA A   1      27.462  14.144   5.469  1.00 20.00           N
ATOM      2  CA  ALA A   1      26.132  14.439   6.109  1.00 20.00           C
ATOM      3  C   ALA A   1      25.170  13.249   6.109  1.00 20.00           C
ATOM      4  O   ALA A   1      25.170  12.249   6.109  1.00 20.00           O
ATOM      5  CB  ALA A   1      26.132  14.439   7.609  1.00 20.00           C
ATOM      6  N   GLY A   2      24.000  13.000   6.000  1.00 20.00           N
ATOM      7  CA  GLY A   2      23.000  14.000   7.000  1.00 20.00           C
ATOM      8  C   GLY A   2      22.000  15.000   8.000  1.00 20.00           C
ATOM      9  O   GLY A   2      21.000  16.000   9.000  1.00 20.00           O
TER      10      GLY A   2
END"""

# TestSuite for fixture generation
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={},
            test_cases=[
                # Test Case 1: Extract chains from PDB
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=BiotiteExtractChainsRequest(
                        items=[
                            BiotiteExtractChainsRequestItem(
                                pdb=_SAMPLE_PDB_MULTI_CHAIN,
                                chain_ids=["A", "B"],
                            )
                        ]
                    ),
                    input_filename_template=GENERATE_INPUT,
                    expected_output_fixture=GENERATE_OUTPUT,
                ),
                # Test Case 2: Compute RMSD between structures
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=BiotiteRMSDRequest(
                        items=[
                            BiotiteRMSDRequestItem(
                                pdb_a=_SAMPLE_PDB_SINGLE_CHAIN,
                                pdb_b=_SAMPLE_PDB_SINGLE_CHAIN,
                                chain_a=["A"],
                                chain_b=["A"],
                            )
                        ]
                    ),
                    input_filename_template=PREDICT_INPUT,
                    expected_output_fixture=PREDICT_OUTPUT,
                    tolerances={"rel_tol": 1e-4},
                ),
            ],
        )
    ],
)


def generate():
    """Configures and runs the fixture generator for biotite model"""
    generator = FixtureGenerator(fixture_generation_suite)
    generator.generate()


if __name__ == "__main__":
    generate()

# Run with: python models/biotite/fixture.py
