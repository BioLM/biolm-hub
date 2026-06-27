import warnings

from Bio.PDB.PDBExceptions import PDBConstructionWarning

from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.esmfold.config import MODEL_FAMILY
from models.esmfold.fixture import (
    MULTICHAIN_INPUT,
    MULTICHAIN_OUTPUT,
    SINGLECHAIN_INPUT,
    SINGLECHAIN_OUTPUT,
)

# Suppress PDB warnings
warnings.simplefilter("ignore", PDBConstructionWarning)

# ESMFold test suite - single variant, multiple test cases per action
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single mapping that applies to the only variant (no variants = empty config)
        VariantTestMapping(
            variant_config={},  # Applies to all (only) variants
            test_cases=[
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=MULTICHAIN_INPUT,
                    expected_output_fixture=MULTICHAIN_OUTPUT,
                    tolerances={
                        "rel_tol": 1e-1,
                        "pdb_rmsd_threshold": 0.5,
                    },
                ),
                ActionTestCase(
                    action_name=ModelActions.FOLD,
                    input_fixture=SINGLECHAIN_INPUT,
                    expected_output_fixture=SINGLECHAIN_OUTPUT,
                    tolerances={
                        "rel_tol": 1e-1,
                        "pdb_rmsd_threshold": 0.5,
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
#   pytest models/esmfold/test.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/esmfold/test.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/esmfold/test.py -n auto --no-cov -v -s                 # both
