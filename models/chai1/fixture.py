from models.chai1.config import MODEL_FAMILY
from models.chai1.schema import (
    Chai1EntityType,
    Chai1Molecule,
    Chai1PredictRequest,
    Chai1PredictRequestInput,
    Chai1PredictRequestParams,
)
from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator

# Test input/output filenames
INPUT_FILE = "input.json"
EXPECTED_OUTPUT_FILE = "expected_output.json"
MSA_INPUT_FILE = "msa_input.json"
MSA_EXPECTED_OUTPUT_FILE = "msa_expected_output.json"

# Canonical short protein chain — the 25-residue prefix of the stability
# reference protein (models.commons.testing.shared_assets.STANDARD_PROTEIN_STABILITY),
# already used inline as a minimal example across this repo (see this model's
# own README.md, plus msa_transformer/, progen2/, esm2/, temberture/, esmfold/,
# zymctrl/ READMEs/fixtures). Kept short and single-chain to keep diffusion
# inference on this model cheap.
_PROTEIN_SEQUENCE = "MKTVRQERLKSIVRILERSKEPVSG"

# Minimal, fast diffusion params shared by both fixtures below — the golden
# comparisons already use a wide rel_tol (0.5) and generous RMSD thresholds
# (this model uses stochastic diffusion for structure generation), so there is
# no need to pay for the slower/higher-quality default settings here.
_FAST_PARAMS = Chai1PredictRequestParams(
    num_trunk_recycles=1,
    num_diffusion_timesteps=50,
    num_diffn_samples=1,
    use_esm_embeddings=False,
    seed=42,
    include=[],
)

# Plain single-chain protein fold, no precomputed MSA alignment.
_single_chain_request = Chai1PredictRequest(
    params=_FAST_PARAMS,
    items=[
        Chai1PredictRequestInput(
            molecules=[
                Chai1Molecule(
                    name="protein_chain",
                    type=Chai1EntityType.PROTEIN,
                    sequence=_PROTEIN_SEQUENCE,
                )
            ]
        )
    ],
)

# Same single chain, but with a precomputed A3M-format MSA alignment attached
# — reuses the exact minimal alignment shape documented in this model's
# README.md ("Protein-DNA complex with MSA alignment" example), trimmed to a
# lone protein chain to keep the golden self-contained and minimal.
_msa_alignment_request = Chai1PredictRequest(
    params=_FAST_PARAMS,
    items=[
        Chai1PredictRequestInput(
            molecules=[
                Chai1Molecule(
                    name="protein_chain",
                    type=Chai1EntityType.PROTEIN,
                    sequence=_PROTEIN_SEQUENCE,
                    alignment={
                        "uniref90": (
                            f">query\n{_PROTEIN_SEQUENCE}\n"
                            f">hit1\n{_PROTEIN_SEQUENCE}\n"
                        ),
                    },
                )
            ]
        )
    ],
)


def _build_fixture_generation_suite() -> TestSuite:
    """Build the fixture-generation suite (single-variant model).

    Inputs are inlined (self-contained), so importing this module never
    touches R2 and `generate()` needs no manually-placed R2 inputs — it
    writes these inputs to R2 alongside the generated outputs.
    """
    return TestSuite(
        model_family=MODEL_FAMILY,
        r2_fixture_subdir="models",
        variant_test_mappings=[
            VariantTestMapping(
                variant_config={},  # Single variant model - applies to all
                test_cases=[
                    # Test Case 1: single protein chain, no MSA
                    ActionTestCase(
                        action_name=ModelActions.FOLD,
                        input_fixture=_single_chain_request,
                        input_filename_template=INPUT_FILE,
                        expected_output_fixture=EXPECTED_OUTPUT_FILE,
                    ),
                    # Test Case 2: single protein chain with a precomputed MSA
                    ActionTestCase(
                        action_name=ModelActions.FOLD,
                        input_fixture=_msa_alignment_request,
                        input_filename_template=MSA_INPUT_FILE,
                        expected_output_fixture=MSA_EXPECTED_OUTPUT_FILE,
                    ),
                ],
            )
        ],
    )


def generate():
    """Configures and runs the fixture generator for Chai-1."""
    generator = FixtureGenerator(_build_fixture_generation_suite())
    generator.generate()


if __name__ == "__main__":
    generate()

# Run with: python models/chai1/fixture.py
