import warnings

from Bio.PDB.PDBExceptions import PDBConstructionWarning

from models.chai1.config import MODEL_FAMILY
from models.chai1.fixture import (
    EXPECTED_OUTPUT_FILE,
    INPUT_FILE,
    MSA_EXPECTED_OUTPUT_FILE,
    MSA_INPUT_FILE,
)
from models.chai1.schema import (
    Chai1EntityType,
    Chai1Molecule,
    Chai1PredictRequest,
    Chai1PredictRequestInput,
    Chai1PredictRequestParams,
)
from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite

# Suppress PDB warnings
warnings.simplefilter("ignore", PDBConstructionWarning)


# Integration test suite - file-based inputs with golden output comparisons
integration_test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={},  # Single variant model - applies to all
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=INPUT_FILE,  # "input.json"
                    expected_output_fixture=EXPECTED_OUTPUT_FILE,  # "expected_output.json"
                    tolerances={
                        # Structural agreement is governed by pdb_rmsd_threshold
                        # (kept loose — this model uses stochastic diffusion).
                        # rel_tol only ever gates scalar fields, so keep it tight:
                        # a passing RMSD contributes 0 to max_diff, so tightening
                        # rel_tol below the RMSD threshold cannot fail the
                        # structure check, but it does bound any confidence scalar
                        # (e.g. plddt/pae, currently disabled) to +/-10% instead of
                        # the previous +/-50%.
                        "rel_tol": 0.1,
                        "pdb_rmsd_threshold": 0.5,
                    },
                ),
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=MSA_INPUT_FILE,  # "msa_input.json"
                    expected_output_fixture=MSA_EXPECTED_OUTPUT_FILE,  # "msa_expected_output.json"
                    tolerances={
                        # See the note above: loose structural threshold, tight
                        # rel_tol for scalar fields.
                        "rel_tol": 0.1,
                        "pdb_rmsd_threshold": 3.5,  # Even higher threshold for MSA test
                    },
                ),
            ],
        )
    ],
)

# Deployment test suite - programmatic input with basic validation only
deployment_test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={},  # Single variant model - applies to all
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=Chai1PredictRequest(
                        params=Chai1PredictRequestParams(
                            num_trunk_recycles=1,
                            num_diffusion_timesteps=50,
                            use_esm_embeddings=False,
                            seed=42,
                            include=[],
                        ),
                        items=[
                            Chai1PredictRequestInput(
                                molecules=[
                                    Chai1Molecule(
                                        name="minimal-protein",
                                        type=Chai1EntityType.PROTEIN,
                                        sequence="A",
                                    )
                                ]
                            )
                        ],
                    ),
                    # No expected_output_fixture = deployment test only (uses default validator)
                ),
            ],
        )
    ],
)

# Generate integration tests (marked with @pytest.mark.integration)
test_chai1_integration = generate_tests_from_suite(
    integration_test_suite, test_type="integration"
)

# Generate deployment tests (marked with @pytest.mark.deployment)
test_chai1_deployment = generate_tests_from_suite(
    deployment_test_suite, test_type="deployment"
)

# Usage:
#   pytest models/chai1/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/chai1/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/chai1/test.py -n auto --no-cov -v -s                 # both
