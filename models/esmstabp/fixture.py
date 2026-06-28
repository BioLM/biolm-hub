from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.commons.testing.shared_assets import STANDARD_PROTEIN_STABILITY
from models.esmstabp.config import MODEL_FAMILY
from models.esmstabp.schema import (
    ESMStabPExperimentalCondition,
    ESMStabPPredictRequest,
    ESMStabPPredictRequestItem,
)

# Fixture filename constants - Model 1 (embedding only)
PREDICT_INPUT = "predict_input.json"
PREDICT_OUTPUT = "predict_expected_output.json"

# Model 2: with growth_temp
PREDICT_WITH_GROWTH_TEMP_INPUT = "predict_with_growth_temp_input.json"
PREDICT_WITH_GROWTH_TEMP_OUTPUT = "predict_with_growth_temp_expected_output.json"

# Model 3: with experimental_condition
PREDICT_WITH_CONDITION_INPUT = "predict_with_condition_input.json"
PREDICT_WITH_CONDITION_OUTPUT = "predict_with_condition_expected_output.json"

# Model 4: all features
PREDICT_ALL_FEATURES_INPUT = "predict_all_features_input.json"
PREDICT_ALL_FEATURES_OUTPUT = "predict_all_features_expected_output.json"

# Test sequences
SEQUENCE_1 = STANDARD_PROTEIN_STABILITY
SEQUENCE_2 = (
    "MEKVYGLIGFPVEHSLSPLMHNDAFARLGIPARYHLFSVEPGQVGAAIAGVRALGIAGVNVTIPHKLAVIPFL"
    "DEVDEHARRIGAVNTIINNDGRLIGFNTDGPGYVQALEEEMNITLDGKRILVIGAGGGARGIYFSLLSTAAE"
    "RIDMANRTVEKAERLVREGEGGRSAYFSLAEAETRLDEYDIIINTTSVGMHPRVEVQPLSLERLRPGVIVS"
    "NIIYNPLETKWLKEAKARGARVQNGVGMLVYQGALAFEKWTGQWPDVNRMKQLVIEALRR"
)

# Create TestSuite for fixture generation
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single variant model - empty config applies to all
        VariantTestMapping(
            variant_config={},
            test_cases=[],
        )
    ],
)


def generate() -> None:
    """Configures and runs the fixture generator."""
    generator = FixtureGenerator(fixture_generation_suite)

    # Test Case 1: Model 1 - embedding only (no metadata)
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=ESMStabPPredictRequest(
                items=[
                    ESMStabPPredictRequestItem(sequence=SEQUENCE_1),
                    ESMStabPPredictRequestItem(sequence=SEQUENCE_2),
                ],
            ),
            input_filename_template=PREDICT_INPUT,
            expected_output_fixture=PREDICT_OUTPUT,
        )
    )

    # Test Case 2: Model 2 - with growth_temp (mesophilic and thermophilic)
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=ESMStabPPredictRequest(
                items=[
                    ESMStabPPredictRequestItem(
                        sequence=SEQUENCE_1,
                        growth_temp=37,  # Mesophilic (human body temp)
                    ),
                    ESMStabPPredictRequestItem(
                        sequence=SEQUENCE_2,
                        growth_temp=75,  # Thermophilic organism
                    ),
                ],
            ),
            input_filename_template=PREDICT_WITH_GROWTH_TEMP_INPUT,
            expected_output_fixture=PREDICT_WITH_GROWTH_TEMP_OUTPUT,
        )
    )

    # Test Case 3: Model 3 - with experimental_condition
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=ESMStabPPredictRequest(
                items=[
                    ESMStabPPredictRequestItem(
                        sequence=SEQUENCE_1,
                        experimental_condition=ESMStabPExperimentalCondition.CELL,
                    ),
                    ESMStabPPredictRequestItem(
                        sequence=SEQUENCE_2,
                        experimental_condition=ESMStabPExperimentalCondition.LYSATE,
                    ),
                ],
            ),
            input_filename_template=PREDICT_WITH_CONDITION_INPUT,
            expected_output_fixture=PREDICT_WITH_CONDITION_OUTPUT,
        )
    )

    # Test Case 4: Model 4 - all features (growth_temp + experimental_condition)
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=ESMStabPPredictRequest(
                items=[
                    ESMStabPPredictRequestItem(
                        sequence=SEQUENCE_1,
                        growth_temp=37,
                        experimental_condition=ESMStabPExperimentalCondition.CELL,
                    ),
                    ESMStabPPredictRequestItem(
                        sequence=SEQUENCE_2,
                        growth_temp=75,
                        experimental_condition=ESMStabPExperimentalCondition.LYSATE,
                    ),
                ],
            ),
            input_filename_template=PREDICT_ALL_FEATURES_INPUT,
            expected_output_fixture=PREDICT_ALL_FEATURES_OUTPUT,
        )
    )

    generator.generate()


if __name__ == "__main__":
    # python models/esmstabp/fixture.py
    generate()
