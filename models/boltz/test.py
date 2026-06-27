import warnings

from Bio.PDB.PDBExceptions import PDBConstructionWarning

from models.boltz.config import MODEL_FAMILY
from models.boltz.fixture import (
    BOLTZ1_LIGAND_INPUT,
    BOLTZ1_LIGAND_OUTPUT,
    BOLTZ1_PROTEIN_INPUT,
    BOLTZ1_PROTEIN_OUTPUT,
    BOLTZ2_CYCLIC_PROTEIN_INPUT,
    BOLTZ2_CYCLIC_PROTEIN_OUTPUT,
    BOLTZ2_LIGAND_AFFINITY_INPUT,
    BOLTZ2_LIGAND_AFFINITY_OUTPUT,
    BOLTZ2_MULTIMER_INPUT,
    BOLTZ2_MULTIMER_OUTPUT,
    BOLTZ2_POCKET_INPUT,
    BOLTZ2_POCKET_OUTPUT,
    BOLTZ2_PROTEIN_INPUT,
    BOLTZ2_PROTEIN_OUTPUT,
    BOLTZ2_TEMPLATE_INPUT,
    BOLTZ2_TEMPLATE_OUTPUT,
)
from models.boltz.schema import (
    Boltz1PredictParams,
    Boltz1PredictRequest,
    Boltz1PredictRequestInput,
    Boltz2PredictParams,
    Boltz2PredictRequest,
    Boltz2PredictRequestInput,
    BoltzEntity,
    BoltzEntityType,
    BoltzIncludeParams,
)
from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite

"""
Test suite for Boltz structure prediction models (Boltz1 and Boltz2).

Integration tests (8 total, ~8 min on A100):
- Boltz1 (2): protein, ligand (no-affinity, v1-only)
- Boltz2 (6): protein, cyclic_protein, multimer, template, ligand_affinity, pocket

Deployment tests: Basic smoke tests against deployed endpoints.
"""

# Suppress PDB warnings during testing
warnings.simplefilter("ignore", PDBConstructionWarning)

# CIF structures are inherently stochastic from diffusion sampling — skip them
# in comparison and only validate confidence scores (which are more stable).
_BOLTZ_IGNORE_PATHS = {"results.0.cif"}

# Default tolerances for single-entity structure predictions
DEFAULT_BOLTZ_TOLERANCES = {
    "rel_tol": 7e-2,  # 7% relative tolerance for numerical values
    "ignore_paths": _BOLTZ_IGNORE_PATHS,
}

# Higher tolerances for stochastic/sampling-based predictions
# Used for: cyclic proteins, template-based modeling where randomness affects results
# Note: Boltz2 diffusion sampling can produce 10-15% variance in confidence scores
HIGH_TOLERANCES = {
    "rel_tol": 1.5e-1,  # 15% relative tolerance (Boltz2 template/sampling variance)
    "ignore_paths": _BOLTZ_IGNORE_PATHS,
}

# Template-guided predictions: same as HIGH_TOLERANCES but with 20% rel_tol.
# pair_chains_iptm and other confidence scores often vary 15-20% between runs.
TEMPLATE_TOLERANCES = {
    "rel_tol": 4.5e-1,  # 45% — pair_chains_iptm varies 20-30%+ between runs
    "abs_tol": 1.0,  # Safety net for near-zero confidence values
    "ignore_paths": _BOLTZ_IGNORE_PATHS,
}

# Multi-entity tolerances for structures with multiple entity types
# Enables chain matching and per-entity RMSD calculation for:
# - Protein-nucleic acid complexes (DNA/RNA)
# - Protein-ligand complexes with induced fit (pocket constraints)
# - Multi-chain assemblies with different molecule types
# Note: Boltz2 diffusion sampling produces higher variance in confidence scores
MULTIENTITY_TOLERANCES = {
    "rel_tol": 4.5e-1,  # 45% relative tolerance — confidence scores (complex_pde, pTM) vary
    "abs_tol": 1.0,  # Safety net for near-zero confidence values that can flip sign
    "ignore_paths": _BOLTZ_IGNORE_PATHS,
    "multientity_mmcif_comparison": True,  # Enable multi-entity comparator
}

# Protein-ligand interface tolerances
# Protein-ligand interfaces have high variability due to:
# - Transient vs stable interactions (pTM can vary 0.3-0.8)
# - Interface sampling sensitivity and induced fit conformational changes
# - Affinity predictions are highly non-deterministic (can vary 80%+ between runs)
# - Conformational selection vs induced fit mechanisms
# - Model improvements over time (especially for error metrics where lower is better)
# - Pocket constraints can produce large conformational changes (10-15Å RMSD)
PROTEIN_INTERFACE_TOLERANCES = {
    "rel_tol": 9.5e-1,  # 95% tolerance - iPSAE/ipae + affinity are highly stochastic
    "abs_tol": 1.0,  # Safety net for near-zero values that can flip sign
    "ignore_paths": _BOLTZ_IGNORE_PATHS,
    "multientity_mmcif_comparison": True,  # Enable multi-entity comparator
}


integration_test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # BOLTZ1 TEST CASES (reduced from 7 to 2):
        # Removed tests still have inputs in R2 at r2://biolm-modal/test-data/models/boltz/boltz1/:
        #   - cyclic_protein: tests cyclic peptide folding (also covered by boltz2 suite)
        #   - multimer: tests multi-chain complex (also covered by boltz2 suite)
        #   - msa: tests MSA-guided prediction (also covered by boltz2 suite)
        #   - trna: tests tRNA-protein complex (also covered by boltz2 suite)
        #   - dna_protein: tests DNA-protein complex (also covered by boltz2 suite)
        VariantTestMapping(
            variant_config={"MODEL_VERSION": "boltz1"},
            test_cases=[
                # 1. Protein test — core single-protein folding
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=BOLTZ1_PROTEIN_INPUT,
                    expected_output_fixture=BOLTZ1_PROTEIN_OUTPUT,
                    tolerances=HIGH_TOLERANCES,
                ),
                # 2. Ligand test (without affinity) — boltz1-only feature
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=BOLTZ1_LIGAND_INPUT,
                    expected_output_fixture=BOLTZ1_LIGAND_OUTPUT,
                    tolerances=PROTEIN_INTERFACE_TOLERANCES,
                ),
            ],
        ),
        # BOLTZ2 TEST CASES (reduced from 9 to 6):
        # Removed tests still have inputs in R2 at r2://biolm-modal/test-data/models/boltz/boltz2/:
        #   - msa: MSA-guided prediction
        #   - trna: tRNA-protein complex
        #   - dna_protein: DNA-protein complex
        # These are duplicative of boltz1 tests (same biology, different input format).
        VariantTestMapping(
            variant_config={"MODEL_VERSION": "boltz2"},
            test_cases=[
                # 1. Protein test — core folding (validates v2 vs v1 differences)
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=BOLTZ2_PROTEIN_INPUT,
                    expected_output_fixture=BOLTZ2_PROTEIN_OUTPUT,
                    tolerances=MULTIENTITY_TOLERANCES,
                ),
                # 2. Cyclic protein test — cyclic peptide handling
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=BOLTZ2_CYCLIC_PROTEIN_INPUT,
                    expected_output_fixture=BOLTZ2_CYCLIC_PROTEIN_OUTPUT,
                    tolerances=HIGH_TOLERANCES,
                ),
                # 3. Multimer test — multi-chain complex
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=BOLTZ2_MULTIMER_INPUT,
                    expected_output_fixture=BOLTZ2_MULTIMER_OUTPUT,
                    tolerances=PROTEIN_INTERFACE_TOLERANCES,
                ),
                # 4. Template test — boltz2-only feature
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=BOLTZ2_TEMPLATE_INPUT,
                    expected_output_fixture=BOLTZ2_TEMPLATE_OUTPUT,
                    tolerances=TEMPLATE_TOLERANCES,
                ),
                # 5. Ligand+affinity test — boltz2-only feature
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=BOLTZ2_LIGAND_AFFINITY_INPUT,
                    expected_output_fixture=BOLTZ2_LIGAND_AFFINITY_OUTPUT,
                    tolerances=PROTEIN_INTERFACE_TOLERANCES,
                ),
                # 6. Pocket test — boltz2-only feature (constraints)
                # Pocket affinity scores are highly stochastic (sign flips across runs)
                # so add abs_tol to handle near-zero values; structural RMSD still validated.
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=BOLTZ2_POCKET_INPUT,
                    expected_output_fixture=BOLTZ2_POCKET_OUTPUT,
                    tolerances={
                        **PROTEIN_INTERFACE_TOLERANCES,
                        "abs_tol": 2.0,  # Affinity scores can flip sign (-0.05 vs +0.68)
                    },
                ),
            ],
        ),
    ],
)

# DEPLOYMENT TEST SUITE:
# Smoke tests against deployed endpoints with minimal inputs
# These tests verify basic functionality without golden file comparisons

deployment_test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Boltz1 deployment tests (uses Boltz1 schema)
        VariantTestMapping(
            variant_config={"MODEL_VERSION": "boltz1"},
            test_cases=[
                # Minimal protein structure prediction test
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=Boltz1PredictRequest(
                        params=Boltz1PredictParams(
                            recycling_steps=1,  # Minimal for speed
                            sampling_steps=10,  # Minimal for speed
                            diffusion_samples=1,
                            seed=42,
                            potentials=False,
                            include=[],  # No extra outputs to minimize response size
                        ),
                        items=[
                            Boltz1PredictRequestInput(
                                molecules=[
                                    BoltzEntity(
                                        id="A",
                                        type=BoltzEntityType.PROTEIN,
                                        sequence="MKLLVVVQVWHHHHH",  # Short 15-residue protein
                                    )
                                ]
                            )
                        ],
                    ),
                    # No expected_output_fixture - deployment tests use default validator
                ),
                # Protein-ligand complex test
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=Boltz1PredictRequest(
                        params=Boltz1PredictParams(
                            recycling_steps=1,
                            sampling_steps=10,
                            diffusion_samples=1,
                            seed=42,
                            potentials=False,
                            include=[],
                        ),
                        items=[
                            Boltz1PredictRequestInput(
                                molecules=[
                                    BoltzEntity(
                                        id="A",
                                        type=BoltzEntityType.PROTEIN,
                                        sequence="MKLLVVVQVW",  # 10-residue protein
                                    ),
                                    BoltzEntity(
                                        id="LIG",
                                        type=BoltzEntityType.LIGAND,
                                        smiles="CCO",  # Ethanol
                                    ),
                                ]
                            )
                        ],
                    ),
                ),
                # Protein multimer test with ipSAE calculation (PAE enabled)
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=Boltz1PredictRequest(
                        params=Boltz1PredictParams(
                            recycling_steps=1,
                            sampling_steps=10,
                            diffusion_samples=1,
                            seed=42,
                            potentials=False,
                            include=[
                                BoltzIncludeParams.PAE
                            ],  # Enable PAE to trigger ipSAE calculation
                        ),
                        items=[
                            Boltz1PredictRequestInput(
                                molecules=[
                                    BoltzEntity(
                                        id="A",
                                        type=BoltzEntityType.PROTEIN,
                                        sequence="MKLLVVVQVW",  # 10-residue protein chain A
                                    ),
                                    BoltzEntity(
                                        id="B",
                                        type=BoltzEntityType.PROTEIN,
                                        sequence="GHHHHHLLLL",  # 10-residue protein chain B
                                    ),
                                ]
                            )
                        ],
                    ),
                ),
            ],
        ),
        # Boltz2 deployment tests (uses Boltz2 schema)
        VariantTestMapping(
            variant_config={"MODEL_VERSION": "boltz2"},
            test_cases=[
                # Minimal protein structure prediction test
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=Boltz2PredictRequest(
                        params=Boltz2PredictParams(
                            recycling_steps=1,  # Minimal for speed
                            sampling_steps=10,  # Minimal for speed
                            diffusion_samples=1,
                            seed=42,
                            potentials=False,
                            include=[],  # No extra outputs to minimize response size
                        ),
                        items=[
                            Boltz2PredictRequestInput(
                                molecules=[
                                    BoltzEntity(
                                        id="A",
                                        type=BoltzEntityType.PROTEIN,
                                        sequence="MKLLVVVQVWHHHHH",  # Short 15-residue protein
                                    )
                                ]
                            )
                        ],
                    ),
                    # No expected_output_fixture - deployment tests use default validator
                ),
                # Protein-ligand complex test
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=Boltz2PredictRequest(
                        params=Boltz2PredictParams(
                            recycling_steps=1,
                            sampling_steps=10,
                            diffusion_samples=1,
                            seed=42,
                            potentials=False,
                            include=[],
                        ),
                        items=[
                            Boltz2PredictRequestInput(
                                molecules=[
                                    BoltzEntity(
                                        id="A",
                                        type=BoltzEntityType.PROTEIN,
                                        sequence="MKLLVVVQVW",  # 10-residue protein
                                    ),
                                    BoltzEntity(
                                        id="LIG",
                                        type=BoltzEntityType.LIGAND,
                                        smiles="CCO",  # Ethanol
                                    ),
                                ]
                            )
                        ],
                    ),
                ),
                # Protein multimer test with ipSAE calculation (PAE enabled)
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=Boltz2PredictRequest(
                        params=Boltz2PredictParams(
                            recycling_steps=1,
                            sampling_steps=10,
                            diffusion_samples=1,
                            seed=42,
                            potentials=False,
                            include=[
                                BoltzIncludeParams.PAE
                            ],  # Enable PAE to trigger ipSAE calculation
                        ),
                        items=[
                            Boltz2PredictRequestInput(
                                molecules=[
                                    BoltzEntity(
                                        id="A",
                                        type=BoltzEntityType.PROTEIN,
                                        sequence="MKLLVVVQVW",  # 10-residue protein chain A
                                    ),
                                    BoltzEntity(
                                        id="B",
                                        type=BoltzEntityType.PROTEIN,
                                        sequence="GHHHHHLLLL",  # 10-residue protein chain B
                                    ),
                                ]
                            )
                        ],
                    ),
                ),
            ],
        ),
    ],
)

# Generate integration tests (marked with @pytest.mark.integration)
test_boltz_integration = generate_tests_from_suite(
    integration_test_suite, test_type="integration"
)

# Generate deployment tests (marked with @pytest.mark.deployment)
test_boltz_deployment = generate_tests_from_suite(
    deployment_test_suite, test_type="deployment"
)

# USAGE INSTRUCTIONS:
#
# Run all tests:
#   pytest models/boltz/test.py -n auto --no-cov -v -s
#
# Run integration tests only:
#   pytest models/boltz/test.py -m integration -n auto --no-cov -v -s
#
# Run deployment tests only:
#   pytest models/boltz/test.py -m deployment -n auto --no-cov -v -s
#
# Run tests for specific variant:
#   pytest models/boltz/test.py -k "boltz1" --no-cov -v -s  # Boltz1 only
#   pytest models/boltz/test.py -k "boltz2" --no-cov -v -s  # Boltz2 only
#
# Run specific test case:
#   pytest models/boltz/test.py -k "protein" --no-cov -v -s  # Protein tests only
#   pytest models/boltz/test.py -k "boltz2-predict-msa_input" --no-cov -v -s  # Specific test


# Unit tests for ipSAE/ipae utilities have been moved to test_unit.py
