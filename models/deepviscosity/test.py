"""
DeepViscosity test suite.

This module defines the test configuration for integration and deployment tests.
"""

from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.deepviscosity.config import MODEL_FAMILY
from models.deepviscosity.fixture import (
    MULTIPLE_AB_INPUT,
    MULTIPLE_PREDICT_OUTPUT,
    SINGLE_AB_INPUT,
    SINGLE_PREDICT_OUTPUT,
    WITH_FEATURES_INPUT,
    WITH_FEATURES_OUTPUT,
)

# DeepViscosity test suite - single variant, multiple test cases
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={},  # Empty dict for single variant
            test_cases=[
                # Test Case 1: Single antibody prediction
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=SINGLE_AB_INPUT,
                    expected_output_fixture=SINGLE_PREDICT_OUTPUT,
                    tolerances={
                        "rel_tol": 1e-4,  # Allow small numerical variance in probabilities
                    },
                ),
                # Test Case 2: Batch prediction (multiple antibodies)
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=MULTIPLE_AB_INPUT,
                    expected_output_fixture=MULTIPLE_PREDICT_OUTPUT,
                    tolerances={
                        "rel_tol": 1e-4,
                    },
                ),
                # Test Case 3: With DeepSP features output
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=WITH_FEATURES_INPUT,
                    expected_output_fixture=WITH_FEATURES_OUTPUT,
                    tolerances={
                        "rel_tol": 1e-4,
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
#   pytest models/deepviscosity/test.py -m integration -n auto --no-cov -v -s
#   pytest models/deepviscosity/test.py -m deployment -n auto --no-cov -v -s
#   pytest models/deepviscosity/test.py -n auto --no-cov -v -s  # both


# Unit tests for schema validation have been moved to test_unit.py
