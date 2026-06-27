import modal
import pytest

from models.chai1.schema import Chai1Params


def _get_edge_case_input():
    """Helper function that returns the edge case input dictionary."""
    return {
        "params": {
            "num_trunk_recycles": 4,
            "num_diffusion_timesteps": 180,
            "num_diffn_samples": 1,
            "use_esm_embeddings": True,
            "seed": 2074,
            "include": [],
        },
        "items": [
            {
                "molecules": [
                    {
                        "name": "SampleProteinA",
                        "type": "protein",
                        "sequence": "ACDEFGHIKL",
                    },
                    {
                        "name": "ProteinWithAlign",
                        "type": "protein",
                        "sequence": "ACDEFGHIKM",
                        "alignment": {"uniref90": ">seq1\nACDEFGHIKM"},
                    },
                    {"name": "SampleDNA", "type": "DNA", "sequence": "ATGCGT"},
                    {"name": "SampleLigand", "type": "ligand", "smiles": "C1=CC=CC=C1"},
                ]
            }
        ],
    }


@pytest.mark.integration
def test_integration_edge_case():
    """Test Chai1 edge case integration with deployed model."""
    app_name = Chai1Params.base_model_slug
    test_input = _get_edge_case_input()

    # Look up the deployed model
    Model = modal.Cls.from_name(app_name, "Chai1Model")
    model = Model()

    # Call the fold method
    response = model.fold.remote(test_input)

    # Basic validation - just check that response has results key
    assert "results" in response, "Response missing 'results' key"
