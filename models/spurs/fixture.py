from models.commons.model.schema import ModelActions
from models.commons.storage.r2 import read_json_from_r2
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.commons.util.config import r2_bucket_name, r2_test_data_dir
from models.spurs.config import MODEL_FAMILY
from models.spurs.schema import (
    SpursPredictRequest,
    SpursPredictRequestItem,
)

# Fixture filename constants
PREDICT_SINGLE_INPUT = "predict_single_input.json"
PREDICT_MULTI_INPUT = "predict_multi_input.json"
PREDICT_SINGLE_OUTPUT = "predict_single_expected_output.json"
PREDICT_MULTI_OUTPUT = "predict_multi_expected_output.json"
PREDICT_MATRIX_INPUT = "predict_matrix_input.json"
PREDICT_MATRIX_OUTPUT = "predict_matrix_expected_output.json"
PREDICT_VARIANT_INPUT = "predict_variant_input.json"
PREDICT_VARIANT_OUTPUT = "predict_variant_expected_output.json"
TSHR260_CIF_FILENAME = "tshr260_chai1_structure.cif"


_R2_BASE_PATH = f"{r2_test_data_dir}/models/{MODEL_FAMILY.base_model_slug}"
r2_key = f"{_R2_BASE_PATH}/{TSHR260_CIF_FILENAME}"
record = read_json_from_r2(r2_bucket_name, r2_key)
_TSHR260_CIF = record.get("tshr260_cif")

# Sample sequence (extracted from tshr260_chai1_structure.cif, chain A)
_SAMPLE_SEQUENCE = (
    "MGCSSPPCECHQEEDFRVTCKDIQRIPSLPPSTQTLKLIETHLRTIPSHAFSNLPNISRIYVSIDVTLQQLESHS"
    "FYNLSKVTHIEIRNTRNLTYIDPDALKELPLLKFLGIFNTGLKMFPDLTKVYSTDIFFILEITDNPYMTSIPVNAF"
    "QGLCNETLTLKLYNNGFTSVQGYAFNGTKLDAVYLNKNKYLTVIDKDAFGGVYSGPSLLDVSQTSVTALPSKGLEH"
    "LKELIARNTWTL"
)

# Create TestSuite for fixture generation with programmatic inputs
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={},
            test_cases=[],
        )
    ],
)


def generate():
    """Configures and runs the fixture generator"""
    generator = FixtureGenerator(fixture_generation_suite)

    # Test Case 1: single mutation prediction
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=SpursPredictRequest(
                items=[
                    SpursPredictRequestItem(
                        sequence=_SAMPLE_SEQUENCE,
                        cif=_TSHR260_CIF,
                        mutations=["P121I"],
                    )
                ]
            ),
            input_filename_template=PREDICT_SINGLE_INPUT,
            expected_output_fixture=PREDICT_SINGLE_OUTPUT,
            tolerances={"rel_tol": 1e-4},
        )
    )

    # Test Case 2: multi-mutation prediction
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=SpursPredictRequest(
                items=[
                    SpursPredictRequestItem(
                        sequence=_SAMPLE_SEQUENCE,
                        cif=_TSHR260_CIF,
                        mutations=["I232R", "P147Y"],
                    )
                ]
            ),
            input_filename_template=PREDICT_MULTI_INPUT,
            expected_output_fixture=PREDICT_MULTI_OUTPUT,
            tolerances={"rel_tol": 1e-4},
        )
    )

    # Test Case 3: full matrix prediction (no explicit mutations)
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=SpursPredictRequest(
                items=[
                    SpursPredictRequestItem(
                        sequence=_SAMPLE_SEQUENCE,
                        cif=_TSHR260_CIF,
                        mutations=None,
                    )
                ]
            ),
            input_filename_template=PREDICT_MATRIX_INPUT,
            expected_output_fixture=PREDICT_MATRIX_OUTPUT,
            tolerances={"rel_tol": 1e-4},
        )
    )

    # Test Case 4: variant_sequence auto-calculation (I232R, P147Y from variant)
    # Create variant sequence with I232R and P147Y mutations
    _VARIANT_SEQUENCE = list(_SAMPLE_SEQUENCE)
    _VARIANT_SEQUENCE[231] = "R"  # I232R (0-indexed: 231)
    _VARIANT_SEQUENCE[146] = "Y"  # P147Y (0-indexed: 146)
    _VARIANT_SEQUENCE = "".join(_VARIANT_SEQUENCE)

    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=SpursPredictRequest(
                items=[
                    SpursPredictRequestItem(
                        sequence=_SAMPLE_SEQUENCE,  # Wild-type
                        variant_sequence=_VARIANT_SEQUENCE,  # Variant with I232R, P147Y
                        cif=_TSHR260_CIF,
                        mutations=None,
                        return_full_dms=False,
                    )
                ]
            ),
            input_filename_template=PREDICT_VARIANT_INPUT,
            expected_output_fixture=PREDICT_VARIANT_OUTPUT,
            tolerances={"rel_tol": 1e-4},
        )
    )

    generator.generate()


if __name__ == "__main__":
    generate()

# Run with: python models/spurs/fixture.py
