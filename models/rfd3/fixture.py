"""Fixture generator for RFdiffusion3 model tests."""

from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.rfd3.config import MODEL_FAMILY
from models.rfd3.schema import (
    RFD3DesignRequest,
)

# Define test inputs inline as Pydantic models
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
            "conditioning_mode": "binder_design",
            "include_trajectories": False,
        },
        "items": [
            {
                "name": "binder_design",
                "components": [
                    {
                        "name": "target",
                        "sequence": "MKKLLFIAVVFTLLGTAVQAAYPYDDAAQLTEEQRKNEELRGQLQPTEGR",
                        "chain_id": "A",
                    },
                    {
                        "name": "binder",
                        "sequence": "MKLLILAVVFTVFGTAVQAAYPYDDAAQLTEEQR",
                        "chain_id": "B",
                    },
                ],
                "target_chain": "A",
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

# Fixture generation suite
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single mapping (no variants)
        VariantTestMapping(
            variant_config={},  # Empty dict means single variant
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=INPUT1,
                    input_filename_template="rfd3-generate-input1.json",
                    expected_output_fixture="rfd3-generate-input1-expected_output.json",
                ),
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=INPUT2,
                    input_filename_template="rfd3-generate-input2.json",
                    expected_output_fixture="rfd3-generate-input2-expected_output.json",
                ),
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=INPUT3,
                    input_filename_template="rfd3-generate-input3.json",
                    expected_output_fixture="rfd3-generate-input3-expected_output.json",
                ),
            ],
        )
    ],
)


def generate():
    """Generate fixtures for RFdiffusion3 model."""
    generator = FixtureGenerator(fixture_generation_suite)
    generator.generate()


if __name__ == "__main__":
    print("🚀 Generating fixtures for RFdiffusion3...")
    generate()
    print("✅ Fixture generation complete!")
