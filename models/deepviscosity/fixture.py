"""
DeepViscosity test fixtures.

This module defines test input/output filenames and fixture generation configuration.
Test sequences are from the DeepViscosity_input.csv sample file.
"""

from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.deepviscosity.config import MODEL_FAMILY
from models.deepviscosity.schema import (
    DeepViscosityPredictRequest,
    DeepViscosityPredictRequestItem,
    DeepViscosityPredictRequestParams,
)

# Test input/output filenames (stored in the model test-data bucket under models/deepviscosity/)
SINGLE_AB_INPUT = "single_ab_input.json"
SINGLE_PREDICT_OUTPUT = "single_predict_expected_output.json"
MULTIPLE_AB_INPUT = "multiple_ab_input.json"
MULTIPLE_PREDICT_OUTPUT = "multiple_predict_expected_output.json"
WITH_FEATURES_INPUT = "with_features_input.json"
WITH_FEATURES_OUTPUT = "with_features_expected_output.json"

# Test sequences from DeepViscosity_input.csv
# mAb1 - expected to be diverse enough for testing
TEST_VH_1 = "EVQLVESGGGLVQPGRSLRLSCAASGFTFDDYAMHWVRQAPGKGLEWVSAITWNSGHIDYADSVEGRFTISRDNAKNSLYLQMNSLRAEDTAVYYCAKVSYLSTASSLDYWGQGTLVTVSS"
TEST_VL_1 = "DIQMTQSPSSLSASVGDRVTITCRASQGIRNYLAWYQQKPGKAPKLLIYAASTLQSGVPSRFSGSGSGTDFTLTISSLQPEDVATYYCQRYNRAPYTFGQGTKVEIK"

# mAb2
TEST_VH_2 = "EVQLVESGGGLVQPGGSLRLSCAASGFTFSDSWIHWVRQAPGKGLEWVAWISPYGGSTYYADSVKGRFTISADTSKNTAYLQMNSLRAEDTAVYYCARRHWPGGFDYWGQGTLVTVSA"
TEST_VL_2 = "DIQMTQSPSSLSASVGDRVTITCRASQDVSTAVAWYQQKPGKAPKLLIYSASFLYSGVPSRFSGSGSGTDFTLTISSLQPEDFATYYCQQYLYHPATFGQGTKVEIK"

# mAb3
TEST_VH_3 = "QVQLKQSGPGLVQPSQSLSITCTVSGFSLTNYGVHWVRQSPGKGLEWLGVIWSGGNTDYNTPFTSRLSINKDNSKSQVFFKMNSLQSNDTAIYYCARALTYYDYEFAYWGQGTLVTVSA"
TEST_VL_3 = "DILLTQSPVILSVSPGERVSFSCRASQSIGTNIHWYQQRTNGSPRLLIKYASESISGIPSRFSGSGSGTDFTLSINSVESEDIADYYCQQNNNWPTTFGAGTKLELK"


# Create TestSuite for fixture generation
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={},  # Single variant model
            test_cases=[],
        )
    ],
)


def generate() -> None:
    """Configure and run the fixture generator for DeepViscosity test cases."""
    generator = FixtureGenerator(fixture_generation_suite)

    # Test Case 1: Single antibody with default params
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=DeepViscosityPredictRequest(
                items=[
                    DeepViscosityPredictRequestItem(
                        heavy_chain=TEST_VH_1,
                        light_chain=TEST_VL_1,
                    )
                ]
            ),
            input_filename_template=SINGLE_AB_INPUT,
            expected_output_fixture=SINGLE_PREDICT_OUTPUT,
        )
    )

    # Test Case 2: Multiple antibodies (batch)
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=DeepViscosityPredictRequest(
                items=[
                    DeepViscosityPredictRequestItem(
                        heavy_chain=TEST_VH_1,
                        light_chain=TEST_VL_1,
                    ),
                    DeepViscosityPredictRequestItem(
                        heavy_chain=TEST_VH_2,
                        light_chain=TEST_VL_2,
                    ),
                    DeepViscosityPredictRequestItem(
                        heavy_chain=TEST_VH_3,
                        light_chain=TEST_VL_3,
                    ),
                ]
            ),
            input_filename_template=MULTIPLE_AB_INPUT,
            expected_output_fixture=MULTIPLE_PREDICT_OUTPUT,
        )
    )

    # Test Case 3: With DeepSP features included
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=DeepViscosityPredictRequest(
                params=DeepViscosityPredictRequestParams(include_deepsp_features=True),
                items=[
                    DeepViscosityPredictRequestItem(
                        heavy_chain=TEST_VH_1,
                        light_chain=TEST_VL_1,
                    )
                ],
            ),
            input_filename_template=WITH_FEATURES_INPUT,
            expected_output_fixture=WITH_FEATURES_OUTPUT,
        )
    )

    generator.generate()


if __name__ == "__main__":
    # Run with: python models/deepviscosity/fixture.py
    generate()
