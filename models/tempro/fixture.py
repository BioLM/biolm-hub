from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.tempro.config import MODEL_FAMILY
from models.tempro.schema import (
    TemproPredictRequest,
    TemproPredictRequestItem,
)

# Fixture filename constants
PREDICT_SINGLE_INPUT = "predict_single_input.json"
PREDICT_BATCH_INPUT = "predict_batch_input.json"
PREDICT_VALIDATION_INPUT = "predict_validation_input.json"
PREDICT_SINGLE_OUTPUT_TPL = "{variant.name}_predict_single_output.json"
PREDICT_BATCH_OUTPUT_TPL = "{variant.name}_predict_batch_output.json"
PREDICT_VALIDATION_OUTPUT_TPL = "{variant.name}_predict_validation_output.json"

# Validation sequences from TEMPRO paper's external validation with known Tms
# Sequences taken verbatim from the paper's external-validation set (experimentals.fasta)
VALIDATION_SEQUENCES = {
    "4IDL": {
        "sequence": "MAKVQLQQSGGGAVQTGGSLKLTCLASGNTASIRAMGWYRRAPGKQREWVASLTTTGTADYGDFVKGRFTISRDNANNAATLQMDSLKPEDTAVYYCNADGRRFDGARWREYESWGQGTQVTISS",
        "tm": 46.75,
    },
    "4TYU": {
        "sequence": "GSHMEVQLVESGGGLVQAGDSLRLSCTASGRTFSRAVMGWFRQAPGKEREFVAAISAAPGTAYYAFYADSVRGRFSISADSAKNTVYLQMNSLKPEDTAVYYCAADLKMQVAAYMNQRSVDYWGQGTQVTVSS",
        "tm": 85.1,
    },
    "4U05": {
        "sequence": "GSHMEVQLVESGGGLVQAGDSLRLSCTASGRTFSRAVMGWFRQAPGKEREFVAAISAAPGTAYYAFYADSVRGRFSIAADSAKNTVYLQMNSLKPEDTAVYYCAADLKMQVAAYMNQRSVDYWGQGTQVTVSS",
        "tm": 84.0,
    },
    "4W68": {
        "sequence": "GSHMEVQLVESGGGLVQAGDSLRLSATASGRTFSRAVMGWFRQAPGKEREFVAAISAAPGTAYYAFYADSVRGRFSISADSAKNTVYLQMNSLKPEDTAVYYVAADLKMQVAAYMNQRSVDYWGQGTQVTVSS",
        "tm": 88.0,
    },
    "4W70": {
        "sequence": "MAEVQLVESGGGLVQAGDSLRLSATASGRTFSRAVMGWFRQAPGKEREFVAAISAAPGTAYYAFYADSVRGRFSISADSAKNTVYLQMNSLKPEDTAVYYVAADLKMQVAAYMNQRSVDYWGQGTQVTVSS",
        "tm": 60.0,
    },
    "5SV3": {
        "sequence": "MAEVQLVESGGGLVQAGDSLRLSCTASGRTLGDYGVAWFRQAPGKEREFVSVISRSTIITDYADSVRGRFSISADSAKNTVYLQMNSLKPEDTAVYYCAVIANPVYATSRNSDDYGHWGQGTQVTVSS",
        "tm": 69.3,
    },
}

# Representative nanobody sequence for single tests (from 4TYU, mid-range length)
SINGLE_TEST_SEQUENCE = VALIDATION_SEQUENCES["4TYU"]["sequence"]

# Batch test sequences (subset of validation sequences)
BATCH_TEST_SEQUENCES = [
    VALIDATION_SEQUENCES["4IDL"]["sequence"],
    VALIDATION_SEQUENCES["4TYU"]["sequence"],
    VALIDATION_SEQUENCES["5SV3"]["sequence"],
    VALIDATION_SEQUENCES["4W70"]["sequence"],
]

# Create TestSuite for fixture generation with programmatic inputs
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single mapping that applies to ALL variants
        VariantTestMapping(
            variant_config={},  # Empty dict means applies to ALL variants
            test_cases=[
                # Test Case 1: Single sequence prediction
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=TemproPredictRequest(
                        items=[TemproPredictRequestItem(sequence=SINGLE_TEST_SEQUENCE)]
                    ),
                    input_filename_template=PREDICT_SINGLE_INPUT,
                    expected_output_fixture=PREDICT_SINGLE_OUTPUT_TPL,
                ),
                # Test Case 2: Batch prediction (4 sequences)
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=TemproPredictRequest(
                        items=[
                            TemproPredictRequestItem(sequence=seq)
                            for seq in BATCH_TEST_SEQUENCES
                        ]
                    ),
                    input_filename_template=PREDICT_BATCH_INPUT,
                    expected_output_fixture=PREDICT_BATCH_OUTPUT_TPL,
                ),
                # Test Case 3: Validation sequences with known Tms (all 6 sequences)
                ActionTestCase(
                    action_name=ModelActions.PREDICT,
                    input_fixture=TemproPredictRequest(
                        items=[
                            TemproPredictRequestItem(sequence=seq_data["sequence"])
                            for seq_data in VALIDATION_SEQUENCES.values()
                        ]
                    ),
                    input_filename_template=PREDICT_VALIDATION_INPUT,
                    expected_output_fixture=PREDICT_VALIDATION_OUTPUT_TPL,
                    # Use relative tolerance since comparator doesn't support abs_tol
                    # 10% relative tolerance accommodates the expected MAE of 4.5-5.5°C
                    tolerances={
                        "rel_tol": 0.1,  # 10% relative tolerance for temperature predictions
                    },
                ),
            ],
        )
    ],
)


def generate():
    """Configures and runs the fixture generator"""
    generator = FixtureGenerator(fixture_generation_suite)
    generator.generate()


if __name__ == "__main__":
    generate()

# Run with: python models/tempro/fixture.py
