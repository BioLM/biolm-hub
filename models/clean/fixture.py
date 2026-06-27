from models.clean.config import MODEL_FAMILY
from models.clean.schema import (
    CLEANEncodeRequest,
    CLEANEncodeRequestItem,
    CLEANPredictRequest,
    CLEANPredictRequestItem,
)
from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator

SINGLE_PREDICT_INPUT = "single_predict_input.json"
BATCH_PREDICT_INPUT = "batch_predict_input.json"
SINGLE_PREDICT_OUTPUT = "single_predict_expected_output.json"
BATCH_PREDICT_OUTPUT = "batch_predict_expected_output.json"
SINGLE_ENCODE_INPUT = "single_encode_input.json"
SINGLE_ENCODE_OUTPUT = "single_encode_expected_output.json"

# Test sequences from enzymes with known EC numbers (UniProt)
# Beta-lactamase (EC 3.5.2.6) - P62593 (TEM-1)
TEST_SEQUENCE_BETA_LACTAMASE = (
    "MSIQHFRVALIPFFAAFCLPVFAHPETLVKVKDAEDQLGARVGYIELDLNSGKILESFRPEERFPMMSTFKVLLCGAVLS"
    "RVDAGQEQLGRRIHYSQNDLVEYSPVTEKHLTDGMTVRELCSAAITMSDNTAANLLLTTIGGPKELTAFLHNMGDHVTRL"
    "DRWEPELNEAIPNDERDTTMPAAMATTLRKLLTGELLTLASRQQLIDWMEADKVAGPLLRSALPAGWFIADKSGAGERGS"
    "RGIIAALGPDGKPSRIVVIYTTGSQATMDERNRQIAEIGASLIKHW"
)

# Alcohol dehydrogenase (EC 1.1.1.1) - P00330 (ADH1 yeast)
TEST_SEQUENCE_ADH = (
    "MSIPETQKGVIFYESHGKLEYKDIPVPKPKANELLINVKYSGVCHTDLHAWHGDWPLPVKLPLVGGHEGAGVVVGMGENV"
    "KGWKIGDYAGIKWLNGSCMACEYCELGNESNCPHADLSGYTHDGSFQQYATADAVQAAHIPQGTDLAQVAPILCAGITVYK"
    "ALKSANLMAGHWVAISGAAGGLGSLAVQYAKAMGYRVLGIDGGEGKEELFRSIGGEVFIDFTKEKDIVGAVLKATDGGAHG"
    "VINVSVSEAAIEASTRYVRANGTTVLVGMPAGAKCCSDVFNQVVKSISIVGSYVGNRADTREALDFFARGLVKSPIKVVG"
    "LSTLPEIYEKMEKGQIVGRYVVDTSK"
)

# Catalase (EC 1.11.1.6) - P04040 (Human catalase, truncated)
TEST_SEQUENCE_CATALASE = (
    "MADSRDPASDQMQHWKEQRAAQKADVLTTGAGNPVGDKLNVITVGPRGPLLVQDVVFTDEMAHFDRERIPERVVHAKGAG"
    "AFGYFEVTHDITKYSKAKVFEHIGKKTPIAVRFSTVAGESGSADTVRDPRGFAVKFYTEDGNWDLVGNNTPIFFIRDALL"
    "FPSFIHSQKRNPQTHLKDPDMVWDFWSLRPESLHQVSFLFSDRGIPDGHRHMNGYGSHTFKLVNANGEAVYCKFHYKTDQ"
    "GIKNLSVEDAARLSQEDPDYGIRDLFNAIATGKYPSWTF"
)


# Create TestSuite for fixture generation with programmatic inputs
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={},  # Single variant model
            test_cases=[
                # Test cases will be added by the generate() function
            ],
        )
    ],
)


def generate():
    """Configure and run the fixture generator."""
    generator = FixtureGenerator(fixture_generation_suite)

    # Test Case 1: Single sequence predict
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=CLEANPredictRequest(
                items=[CLEANPredictRequestItem(sequence=TEST_SEQUENCE_BETA_LACTAMASE)]
            ),
            input_filename_template=SINGLE_PREDICT_INPUT,
            expected_output_fixture=SINGLE_PREDICT_OUTPUT,
        )
    )

    # Test Case 2: Batch sequences predict
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.PREDICT,
            input_fixture=CLEANPredictRequest(
                items=[
                    CLEANPredictRequestItem(sequence=TEST_SEQUENCE_BETA_LACTAMASE),
                    CLEANPredictRequestItem(sequence=TEST_SEQUENCE_ADH),
                    CLEANPredictRequestItem(sequence=TEST_SEQUENCE_CATALASE),
                ]
            ),
            input_filename_template=BATCH_PREDICT_INPUT,
            expected_output_fixture=BATCH_PREDICT_OUTPUT,
        )
    )

    # Test Case 3: Single sequence encode
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.ENCODE,
            input_fixture=CLEANEncodeRequest(
                items=[CLEANEncodeRequestItem(sequence=TEST_SEQUENCE_BETA_LACTAMASE)]
            ),
            input_filename_template=SINGLE_ENCODE_INPUT,
            expected_output_fixture=SINGLE_ENCODE_OUTPUT,
        )
    )

    generator.generate()


if __name__ == "__main__":
    # python models/clean/fixture.py
    generate()
