from models.commons.core.logging import get_logger
from models.commons.model.schema import ModelActions
from models.commons.testing.config import (
    ActionTestCase,
    TestSuite,
    VariantTestMapping,
)
from models.commons.testing.fixture import FixtureGenerator
from models.thermompnn.config import MODEL_FAMILY
from models.thermompnn.schema import (
    ThermoMPNNPredictParams,
    ThermoMPNNPredictRequest,
    ThermoMPNNPredictRequestItem,
)

logger = get_logger(__name__)

# Test input/output filenames
INPUT1 = "input1.json"
INPUT2 = "input2.json"
INPUT3 = "input3.json"
INPUT4 = "input4.json"  # SSM scan (no mutations)

# Sample PDB structure (extended protein for SSM scan testing - 10 residues)
_SAMPLE_PDB = """ATOM      1  N   MET A   1      20.154  16.967  10.410  1.00 20.00           N
ATOM      2  CA  MET A   1      19.032  16.129  10.012  1.00 20.00           C
ATOM      3  C   MET A   1      17.665  16.839  10.012  1.00 20.00           C
ATOM      4  O   MET A   1      17.615  18.065  10.012  1.00 20.00           O
ATOM      5  CB  MET A   1      19.032  14.848  10.810  1.00 20.00           C
ATOM      6  CG  MET A   1      19.032  13.568  10.012  1.00 20.00           C
ATOM      7  SD  MET A   1      19.032  12.288  10.810  1.00 20.00           S
ATOM      8  CE  MET A   1      19.032  11.008  10.012  1.00 20.00           C
ATOM      9  N   VAL A   2      16.497  16.129  10.012  1.00 20.00           N
ATOM     10  CA  VAL A   2      15.130  16.839  10.012  1.00 20.00           C
ATOM     11  C   VAL A   2      13.763  16.129  10.012  1.00 20.00           C
ATOM     12  O   VAL A   2      13.713  14.903  10.012  1.00 20.00           O
ATOM     13  CB  VAL A   2      15.130  16.839  11.610  1.00 20.00           C
ATOM     14  CG1 VAL A   2      13.763  16.129  12.210  1.00 20.00           C
ATOM     15  CG2 VAL A   2      16.497  16.129  12.210  1.00 20.00           C
ATOM     16  N   LEU A   3      12.595  16.839  10.012  1.00 20.00           N
ATOM     17  CA  LEU A   3      11.228  16.129  10.012  1.00 20.00           C
ATOM     18  C   LEU A   3       9.861  16.839  10.012  1.00 20.00           C
ATOM     19  O   LEU A   3       9.811  18.065  10.012  1.00 20.00           O
ATOM     20  CB  LEU A   3      11.228  14.848  10.810  1.00 20.00           C
ATOM     21  CG  LEU A   3      11.228  13.568  10.012  1.00 20.00           C
ATOM     22  CD1 LEU A   3      11.228  12.288  10.810  1.00 20.00           C
ATOM     23  CD2 LEU A   3      11.228  11.008  10.012  1.00 20.00           C
ATOM     24  N   ALA A   4       8.693  16.129  10.012  1.00 20.00           N
ATOM     25  CA  ALA A   4       7.326  16.839  10.012  1.00 20.00           C
ATOM     26  C   ALA A   4       5.959  16.129  10.012  1.00 20.00           C
ATOM     27  O   ALA A   4       5.909  14.903  10.012  1.00 20.00           O
ATOM     28  CB  ALA A   4       7.326  16.839  11.610  1.00 20.00           C
ATOM     29  N   GLY A   5       4.791  16.839  10.012  1.00 20.00           N
ATOM     30  CA  GLY A   5       3.424  16.129  10.012  1.00 20.00           C
ATOM     31  C   GLY A   5       2.057  16.839  10.012  1.00 20.00           C
ATOM     32  O   GLY A   5       2.007  18.065  10.012  1.00 20.00           O
ATOM     33  N   SER A   6       0.889  16.129  10.012  1.00 20.00           N
ATOM     34  CA  SER A   6      -0.478  16.839  10.012  1.00 20.00           C
ATOM     35  C   SER A   6      -1.845  16.129  10.012  1.00 20.00           C
ATOM     36  O   SER A   6      -1.895  14.903  10.012  1.00 20.00           O
ATOM     37  CB  SER A   6      -0.478  16.839  11.610  1.00 20.00           C
ATOM     38  OG  SER A   6      -1.845  16.129  12.210  1.00 20.00           O
ATOM     39  N   THR A   7      -3.013  16.839  10.012  1.00 20.00           N
ATOM     40  CA  THR A   7      -4.380  16.129  10.012  1.00 20.00           C
ATOM     41  C   THR A   7      -5.747  16.839  10.012  1.00 20.00           C
ATOM     42  O   THR A   7      -5.797  18.065  10.012  1.00 20.00           O
ATOM     43  CB  THR A   7      -4.380  16.839  11.610  1.00 20.00           C
ATOM     44  OG1 THR A   7      -5.747  16.129  12.210  1.00 20.00           O
ATOM     45  CG2 THR A   7      -4.380  14.848  12.210  1.00 20.00           C
ATOM     46  N   ASP A   8      -6.915  16.129  10.012  1.00 20.00           N
ATOM     47  CA  ASP A   8      -8.282  16.839  10.012  1.00 20.00           C
ATOM     48  C   ASP A   8      -9.649  16.129  10.012  1.00 20.00           C
ATOM     49  O   ASP A   8      -9.699  14.903  10.012  1.00 20.00           O
ATOM     50  CB  ASP A   8      -8.282  16.839  11.610  1.00 20.00           C
ATOM     51  CG  ASP A   8      -9.649  16.129  12.210  1.00 20.00           C
ATOM     52  OD1 ASP A   8     -10.817  16.839  12.210  1.00 20.00           O
ATOM     53  OD2 ASP A   8      -9.649  14.903  12.210  1.00 20.00           O
ATOM     54  N   GLU A   9     -10.817  16.839  10.012  1.00 20.00           N
ATOM     55  CA  GLU A   9     -12.184  16.129  10.012  1.00 20.00           C
ATOM     56  C   GLU A   9     -13.551  16.839  10.012  1.00 20.00           C
ATOM     57  O   GLU A   9     -13.601  18.065  10.012  1.00 20.00           O
ATOM     58  CB  GLU A   9     -12.184  16.839  11.610  1.00 20.00           C
ATOM     59  CG  GLU A   9     -13.551  16.129  12.210  1.00 20.00           C
ATOM     60  CD  GLU A   9     -14.919  16.839  12.210  1.00 20.00           C
ATOM     61  OE1 GLU A   9     -16.087  16.129  12.210  1.00 20.00           O
ATOM     62  OE2 GLU A   9     -14.919  18.065  12.210  1.00 20.00           O
ATOM     63  N   LYS A  10     -15.087  16.129  10.012  1.00 20.00           N
ATOM     64  CA  LYS A  10     -16.454  16.839  10.012  1.00 20.00           C
ATOM     65  C   LYS A  10     -17.821  16.129  10.012  1.00 20.00           C
ATOM     66  O   LYS A  10     -17.871  14.903  10.012  1.00 20.00           O
ATOM     67  CB  LYS A  10     -16.454  16.839  11.610  1.00 20.00           C
ATOM     68  CG  LYS A  10     -17.821  16.129  12.210  1.00 20.00           C
ATOM     69  CD  LYS A  10     -19.189  16.839  12.210  1.00 20.00           C
ATOM     70  CE  LYS A  10     -20.557  16.129  12.210  1.00 20.00           C
ATOM     71  NZ  LYS A  10     -21.925  16.839  12.210  1.00 20.00           N
END
"""

# Create TestSuite for fixture generation
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={},
            test_cases=[],
        )
    ],
)


def generate():
    """
    Configures and runs the fixture generator for ThermoMPNN model.
    """
    generator = FixtureGenerator(fixture_generation_suite)

    # Test Case 1: Single mutation
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=ThermoMPNNPredictRequest(
                params=ThermoMPNNPredictParams(chain=None),
                items=[
                    ThermoMPNNPredictRequestItem(
                        pdb=_SAMPLE_PDB,
                        mutations=["M1V", "V2A"],
                    )
                ],
            ),
            input_filename_template=INPUT1,
            expected_output_fixture="thermompnn-predict-input1-expected_output.json",
        )
    )

    # Test Case 2: Multiple mutations
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=ThermoMPNNPredictRequest(
                params=ThermoMPNNPredictParams(chain="A"),
                items=[
                    ThermoMPNNPredictRequestItem(
                        pdb=_SAMPLE_PDB,
                        mutations=["L3I", "M1L"],
                    )
                ],
            ),
            input_filename_template=INPUT2,
            expected_output_fixture="thermompnn-predict-input2-expected_output.json",
        )
    )

    # Test Case 3: Single mutation with specific chain
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=ThermoMPNNPredictRequest(
                params=ThermoMPNNPredictParams(chain="A"),
                items=[
                    ThermoMPNNPredictRequestItem(
                        pdb=_SAMPLE_PDB,
                        mutations=["V2F"],
                    )
                ],
            ),
            input_filename_template=INPUT3,
            expected_output_fixture="thermompnn-predict-input3-expected_output.json",
        )
    )

    # Test Case 4: SSM scan (no mutations provided)
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=ThermoMPNNPredictRequest(
                params=ThermoMPNNPredictParams(chain="A"),
                items=[
                    ThermoMPNNPredictRequestItem(
                        pdb=_SAMPLE_PDB,
                        mutations=None,  # Triggers SSM scan
                    )
                ],
            ),
            input_filename_template=INPUT4,
            expected_output_fixture="thermompnn-predict-input4-expected_output.json",
        )
    )

    generator.generate()


if __name__ == "__main__":
    logger.info("Generating fixtures for ThermoMPNN...")
    generate()
