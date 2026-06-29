"""Fixture generator for RosettaFold3 (RF3) model tests."""

from models.commons.core.logging import get_logger
from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.rf3.config import MODEL_FAMILY
from models.rf3.schema import (
    RF3PredictRequest,
)

logger = get_logger(__name__)

# Define test inputs inline as Pydantic models
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

# Small MSA test input (2-line MSA)
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

# Fixture generation suite — all four test cases
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single mapping (no variants)
        VariantTestMapping(
            variant_config={},  # Empty dict means single variant
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=INPUT1,
                    input_filename_template="rf3-predict-input1.json",
                    expected_output_fixture="rf3-predict-input1-expected_output.json",
                ),
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=INPUT2,
                    input_filename_template="rf3-predict-input2.json",
                    expected_output_fixture="rf3-predict-input2-expected_output.json",
                ),
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=INPUT3,
                    input_filename_template="rf3-predict-input3.json",
                    expected_output_fixture="rf3-predict-input3-expected_output.json",
                ),
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=INPUT4_MSA,
                    input_filename_template="rf3-predict-input4-msa.json",
                    expected_output_fixture="rf3-predict-input4-msa-expected_output.json",
                ),
            ],
        )
    ],
)


def generate():
    """Generate fixtures for RosettaFold3 model."""
    generator = FixtureGenerator(fixture_generation_suite)
    generator.generate()


if __name__ == "__main__":
    logger.info("Generating fixtures for RosettaFold3...")
    generate()
    logger.info("Fixture generation complete!")
