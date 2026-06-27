"""Tests for RosettaFold3 (RF3) model."""

from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.rf3.config import MODEL_FAMILY
from models.rf3.schema import (
    RF3PredictRequest,
)

# Define test inputs inline as Pydantic models (same as fixture.py)
INPUT1 = RF3PredictRequest.model_validate(
    {
        "params": {
            "n_recycles": 3,
            "num_steps": 50,
            "diffusion_batch_size": 1,
            "seed": 42,
            "early_stopping_plddt_threshold": 0.5,
            "include_plddt": True,
            "include_pae": False,
        },
        "items": [
            {
                "name": "simple_protein_fold",
                "components": [
                    {
                        "name": "protein_chain",
                        "type": "protein",
                        "sequence": "MKLLILAVVFTVFGTAVQAAYPYDDAAQLTEEQRKNEELRGQLQPTEGRPVEMDAPPSTGPIQRLANMLYTGIISFWMCSGNMLWVFFPVVLFWALVQY",
                        "chain_id": "A",
                    }
                ],
            }
        ],
    }
)

INPUT2 = RF3PredictRequest.model_validate(
    {
        "params": {
            "n_recycles": 5,
            "num_steps": 100,
            "diffusion_batch_size": 2,
            "seed": 123,
            "include_plddt": True,
        },
        "items": [
            {
                "name": "protein_ligand_complex",
                "components": [
                    {
                        "name": "protein",
                        "type": "protein",
                        "sequence": "MKKLLFIAVVFTLLGTAVQAAYPYDDAAQLTEEQRKNEELRGQLQPTEGR",
                        "chain_id": "A",
                    },
                    {
                        "name": "ligand",
                        "type": "ligand",
                        "smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
                        "chain_id": "B",
                    },
                ],
            }
        ],
    }
)

INPUT3 = RF3PredictRequest.model_validate(
    {
        "params": {
            "n_recycles": 8,
            "num_steps": 150,
            "diffusion_batch_size": 3,
            "seed": 999,
            "include_plddt": True,
            "include_pae": False,
        },
        "items": [
            {
                "name": "multi_chain_complex",
                "components": [
                    {
                        "name": "chain_a",
                        "type": "protein",
                        "sequence": "MKLLISLAVVFTVFGTAVQAAYPYDDAAQLTEEQR",
                        "chain_id": "A",
                    },
                    {
                        "name": "chain_b",
                        "type": "protein",
                        "sequence": "GPVEMDAPPSTGPIQRLANMLYTGIISFWMCSGNM",
                        "chain_id": "B",
                    },
                ],
            }
        ],
    }
)

# Small MSA test input
INPUT4_MSA = RF3PredictRequest.model_validate(
    {
        "params": {
            "n_recycles": 3,
            "num_steps": 50,
            "diffusion_batch_size": 1,
            "seed": 42,
            "include_plddt": True,
        },
        "items": [
            {
                "name": "msa_test",
                "components": [
                    {
                        "name": "protein",
                        "type": "protein",
                        "sequence": "MKLLILAVVFTVFGTAVQAAYPYDDAAQLTEEQR",
                        "chain_id": "A",
                        "msa_content": ">seq1\nMKLLILAVVFTVFGTAVQAAYPYDDAAQLTEEQR\n>seq2\nMKLLILAVVFTVFGTAVQAAYPYDDAAQLTEEQR",
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
                    action_name=ModelActions.PREDICT,
                    input_fixture=INPUT1,
                    expected_output_fixture="rf3-predict-input1-expected_output.json",
                    tolerances={
                        "rel_tol": 1e-2,  # Allow 1% relative tolerance for confidence scores
                        "pdb_rmsd_threshold": 5.0,  # Allow 5Å RMSD for structure comparison
                        "multientity_mmcif_comparison": True,  # Enable multi-entity CIF comparison
                    },
                ),
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=INPUT2,
                    expected_output_fixture="rf3-predict-input2-expected_output.json",
                    tolerances={
                        "rel_tol": 1e-2,  # Allow 1% relative tolerance for confidence scores
                        "pdb_rmsd_threshold": 5.0,  # Allow 5Å RMSD for structure comparison
                        "multientity_mmcif_comparison": True,  # Enable multi-entity CIF comparison
                    },
                ),
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=INPUT3,
                    expected_output_fixture="rf3-predict-input3-expected_output.json",
                    tolerances={
                        "rel_tol": 1e-2,  # Allow 1% relative tolerance for confidence scores
                        "pdb_rmsd_threshold": 5.0,  # Allow 5Å RMSD for structure comparison
                        "multientity_mmcif_comparison": True,  # Enable multi-entity CIF comparison
                    },
                ),
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=INPUT4_MSA,
                    expected_output_fixture="rf3-predict-input4-msa-expected_output.json",
                    tolerances={
                        "rel_tol": 1e-2,
                        "pdb_rmsd_threshold": 5.0,
                        "multientity_mmcif_comparison": True,
                    },
                ),
            ],
        )
    ],
)

# Generate integration tests (marked with @pytest.mark.integration)
generate_tests_from_suite(test_suite, test_type="integration")

# Generate deployment tests (marked with @pytest.mark.deployment)
generate_tests_from_suite(test_suite, test_type="deployment")

# Usage:
#   pytest models/rf3/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/rf3/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/rf3/test.py -n auto --no-cov -v -s                 # both
