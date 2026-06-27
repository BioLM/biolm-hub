"""Tests for RFdiffusion3 model."""

from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.rfd3.config import MODEL_FAMILY
from models.rfd3.schema import (
    RFD3DesignRequest,
)


def _validate_rfd3_generate(actual_output: dict, _expected_output: dict | None = None):
    """Validator for RFD3 generate method.

    RFD3 is a generative diffusion model that creates new protein designs.
    Each run produces different structures, so we validate:
    - Results exist and are non-empty
    - Each result has a valid structure_cif
    - The CIF structure can be parsed (is valid)
    - Number of results matches the diffusion_batch_size
    """
    from io import StringIO

    from Bio.PDB.MMCIFParser import MMCIFParser

    assert "results" in actual_output, "Response missing 'results' key"
    assert len(actual_output["results"]) > 0, "Results list is empty"

    # Check each result item
    for item_idx, item in enumerate(actual_output["results"]):
        assert isinstance(item, list), f"Result {item_idx} should be a list of designs"
        assert len(item) > 0, f"Result {item_idx} list is empty"

        # Check each design in the result
        for design_idx, design in enumerate(item):
            assert (
                "structure_cif" in design
            ), f"Design {item_idx}[{design_idx}] missing 'structure_cif'"
            structure_cif = design["structure_cif"]
            assert isinstance(
                structure_cif, str
            ), f"Design {item_idx}[{design_idx}] structure_cif should be a string"
            assert (
                len(structure_cif) > 0
            ), f"Design {item_idx}[{design_idx}] structure_cif is empty"

            # Validate that the CIF can be parsed (is a valid structure)
            try:
                parser = MMCIFParser(QUIET=True)
                io = StringIO(structure_cif)
                structure = parser.get_structure(f"design_{item_idx}_{design_idx}", io)
                assert (
                    structure is not None
                ), f"Design {item_idx}[{design_idx}] CIF failed to parse"

                # Check that structure has atoms
                atoms = list(structure.get_atoms())
                assert (
                    len(atoms) > 0
                ), f"Design {item_idx}[{design_idx}] structure has no atoms"
            except Exception as e:
                raise AssertionError(
                    f"Design {item_idx}[{design_idx}] CIF parsing failed: {e}"
                ) from e


# Define test inputs inline as Pydantic models (same as fixture.py)
INPUT1 = RFD3DesignRequest.model_validate(
    {
        "params": {
            "num_diffusion_steps": 100,
            "diffusion_batch_size": 1,
            "seed": 42,
            "temperature": 1.0,
            "conditioning_mode": "unconditional",
            "include_trajectories": False,
        },
        "items": [
            {
                "name": "simple_design",
                "components": [
                    {
                        "name": "protein",
                        "sequence": "MKLLILAVVFTVFGTAVQAAYPYDDAAQLTEEQRKNEELRGQLQPTEGRPVEMDAPPSTGPIQRLANMLYTGIISFWMCSGNMLWVFFPVVLFWALVQY",
                    }
                ],
            }
        ],
    }
)

INPUT2 = RFD3DesignRequest.model_validate(
    {
        "params": {
            "num_diffusion_steps": 150,
            "diffusion_batch_size": 2,
            "seed": 123,
            "temperature": 0.8,
            "conditioning_mode": "unconditional",
            "include_trajectories": False,
        },
        "items": [
            {
                "name": "multi_component_design",
                "components": [
                    {
                        "name": "chain_a",
                        "sequence": "MKKLLFIAVVFTLLGTAVQAAYPYDDAAQLTEEQRKNEELRGQLQPTEGR",
                        "chain_id": "A",
                    },
                    {
                        "name": "chain_b",
                        "sequence": "MKLLILAVVFTVFGTAVQAAYPYDDAAQLTEEQR",
                        "chain_id": "B",
                    },
                ],
            }
        ],
    }
)

INPUT3 = RFD3DesignRequest.model_validate(
    {
        "params": {
            "num_diffusion_steps": 200,
            "diffusion_batch_size": 1,
            "seed": 999,
            "temperature": 1.2,
            "conditioning_mode": "symmetric_design",
            "symmetry": "C3",
            "include_trajectories": False,
        },
        "items": [
            {
                "name": "symmetric_design",
                "components": [
                    {
                        "name": "monomer",
                        "sequence": "MKLLILAVVFTVFGTAVQAAYPYDDAAQLTEEQRKNEELRGQLQPTEGRPVEMDAPP",
                    }
                ],
            }
        ],
    }
)

# Test suite
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={},  # Single variant
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=INPUT1,
                    expected_output_fixture=None,  # No expected output - validate structure existence only
                    validator=_validate_rfd3_generate,
                ),
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=INPUT2,
                    expected_output_fixture=None,  # No expected output - validate structure existence only
                    validator=_validate_rfd3_generate,
                ),
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=INPUT3,
                    expected_output_fixture=None,  # No expected output - validate structure existence only
                    validator=_validate_rfd3_generate,
                ),
            ],
        )
    ],
)

# Generate integration tests (marked with @pytest.mark.integration)
test_rfd3_integration = generate_tests_from_suite(test_suite, test_type="integration")

# Generate deployment tests (marked with @pytest.mark.deployment)
test_rfd3_deployment = generate_tests_from_suite(test_suite, test_type="deployment")

# Usage:
#   pytest models/rfd3/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/rfd3/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/rfd3/test.py -n auto --no-cov -v -s                 # both
