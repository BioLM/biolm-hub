from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.propermab.config import MODEL_FAMILY
from models.propermab.schema import (
    ProperMABExtractFeaturesParams,
    ProperMABExtractFeaturesRequest,
    ProperMABExtractFeaturesRequestItem,
    ProperMABIsotype,
    ProperMABLightChainType,
)

# Test sequences from Pembrolizumab (Keytruda) - well-characterized therapeutic mAb
# Source: Original ProperMAB repository test data (tests/pembrolizumab_vh.fasta, pembrolizumab_vl.fasta)
# These sequences represent the variable (Fv) domains of a clinically validated antibody
PEMBROLIZUMAB_VH = "QVQLVQSGVEVKKPGASVKVSCKASGYTFTNYYMYWVRQAPGQGLEWMGGINPSNGGTNFNEKFKNRVTLTTDSSTTTAYMELKSLQFDDTAVYYCARRDYRFDMGFDYWGQGTTVTVSS"
PEMBROLIZUMAB_VL = "EIVLTQSPATLSLSPGERATLSCRASKGVSTSGYSYLHWYQQKPGQAPRLLIYLASYLESGVPARFSGSGSGTDFTLTISSLEPEDFAVYYCQHSRDLPLTFGGGTKVEIK"

# Fixture filename constants
# Default parameters test (single run, standard settings)
EXTRACT_FEATURES_DEFAULT_INPUT = "extract_features_default_input.json"
EXTRACT_FEATURES_DEFAULT_OUTPUT = "extract_features_default_expected_output.json"

# Multiple runs test with parameter variations (tests averaging and different isotype/lc_type)
EXTRACT_FEATURES_MULTIRUN_INPUT = "extract_features_multirun_input.json"
EXTRACT_FEATURES_MULTIRUN_OUTPUT = "extract_features_multirun_expected_output.json"

# Create TestSuite for fixture generation with programmatic inputs
# ProperMAB has a single variant (no axes), so variant_config is empty
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={},  # Empty dict for single variant (no variant axes)
            test_cases=[
                # Test Case 1: Default parameters - Basic feature extraction
                # Purpose: Smoke test with standard settings
                # - Single structure prediction run (fastest, deterministic with seed)
                # - Default isotype (IgG1) and light chain type (kappa)
                # - Fv-only sequences (is_fv=True)
                # - Tests all 34 features (7 sequence + 27 structure)
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=ProperMABExtractFeaturesRequest(
                        items=[
                            ProperMABExtractFeaturesRequestItem(
                                heavy_seq=PEMBROLIZUMAB_VH,
                                light_seq=PEMBROLIZUMAB_VL,
                            )
                        ],
                        params=ProperMABExtractFeaturesParams(
                            num_runs=1,  # Single run for deterministic output
                            is_fv=True,  # Fv domain only (affects charge calculations)
                            isotype=ProperMABIsotype.IgG1,  # Standard IgG1 isotype
                            lc_type=ProperMABLightChainType.KAPPA,  # Kappa light chain
                            seed=42,  # Fixed seed for reproducibility
                        ),
                    ),
                    input_filename_template=EXTRACT_FEATURES_DEFAULT_INPUT,
                    expected_output_fixture=EXTRACT_FEATURES_DEFAULT_OUTPUT,
                    tolerances={
                        "rel_tol": 1e-3,  # 0.1% relative tolerance
                    },
                ),
                # Test Case 2: Multiple runs with parameter variations
                # Purpose: Test averaging logic and parameter sensitivity
                # - 3 structure prediction runs (tests averaging of structure features)
                # - Full-length antibody (is_fv=False, includes Fc domain)
                # - IgG2 isotype (tests different Fc charge calculation)
                # - Lambda light chain (tests LC type variation)
                # - Validates integer feature handling (mode/rounding for aromatic_cdr, etc.)
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=ProperMABExtractFeaturesRequest(
                        items=[
                            ProperMABExtractFeaturesRequestItem(
                                heavy_seq=PEMBROLIZUMAB_VH,
                                light_seq=PEMBROLIZUMAB_VL,
                            )
                        ],
                        params=ProperMABExtractFeaturesParams(
                            num_runs=3,  # Multiple runs to test averaging
                            is_fv=False,  # Full-length antibody (not Fv-only)
                            isotype=ProperMABIsotype.IgG2,  # Different isotype
                            lc_type=ProperMABLightChainType.LAMBDA,  # Lambda LC
                            seed=42,  # Same seed for consistency
                        ),
                    ),
                    input_filename_template=EXTRACT_FEATURES_MULTIRUN_INPUT,
                    expected_output_fixture=EXTRACT_FEATURES_MULTIRUN_OUTPUT,
                    tolerances={
                        "rel_tol": 1e-3,  # 0.1% relative tolerance
                    },
                ),
            ],
        )
    ],
)


def generate():
    """Generate fixture outputs by running the ProperMAB app locally via Modal.

    This function:
    1. Uploads programmatic input JSON files to R2 storage
    2. Runs the predict method via Modal locally
    3. Saves the actual outputs to R2 as expected output files

    The generated fixtures are then used by test.py to verify model behavior
    in both integration tests (local Modal runs) and deployment tests (live endpoints).

    Expected runtime: ~4-7 minutes total
    - Test 1: ~60 seconds (1 structure prediction run)
    - Test 2: ~3-5 minutes (3 structure prediction runs)

    Note: Requires Modal authentication and R2 access configured.
    """
    generator = FixtureGenerator(fixture_generation_suite)
    generator.generate()


if __name__ == "__main__":
    generate()

# Run with: python models/propermab/fixture.py
# Outputs will be uploaded to: r2://biolm-modal/test-data/models/propermab/
