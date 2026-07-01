from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.commons.testing.shared_assets import STANDARD_PROTEIN
from models.dsm.config import MODEL_FAMILY
from models.dsm.schema import (
    DSMEncodeIncludeOptions,
    DSMEncodeRequest,
    DSMEncodeRequestItem,
    DSMEncodeRequestParams,
    DSMGenerateRequest,
    DSMGenerateRequestItem,
    DSMGenerateRequestParams,
    DSMRemaskingStrategy,
    DSMScoreRequest,
    DSMScoreRequestItem,
)

GENERATE_UNCONDITIONAL_INPUT = "generate_unconditional_input.json"
GENERATE_MASKED_INPUT = "generate_masked_input.json"
GENERATE_CONDITIONAL_INPUT = "generate_conditional_input.json"
ENCODE_MEAN_INPUT = "encode_mean_input.json"
ENCODE_PER_RESIDUE_INPUT = "encode_per_residue_input.json"
SCORE_INPUT = "score_input.json"

GENERATE_UNCONDITIONAL_OUTPUT_TPL = (
    "{variant.name}_generate_unconditional_expected_output.json"
)
GENERATE_MASKED_OUTPUT_TPL = "{variant.name}_generate_masked_expected_output.json"
GENERATE_CONDITIONAL_OUTPUT_TPL = (
    "{variant.name}_generate_conditional_expected_output.json"
)
ENCODE_MEAN_OUTPUT_TPL = "{variant.name}_encode_mean_expected_output.json"
ENCODE_PER_RESIDUE_OUTPUT_TPL = "{variant.name}_encode_per_residue_expected_output.json"
SCORE_OUTPUT_TPL = "{variant.name}_score_expected_output.json"


# Create TestSuite for fixture generation with programmatic inputs
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Base models (150m-base, 650m-base)
        VariantTestMapping(
            variant_config={"VARIANT": "base"},
            test_cases=[
                # Test Case 1: generate() with unconditional generation (base models)
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=DSMGenerateRequest(
                        params=DSMGenerateRequestParams(
                            num_sequences=3,
                            temperature=1.0,
                            max_length=50,
                            step_divisor=100,
                            remasking=DSMRemaskingStrategy.RANDOM,
                        ),
                        items=[
                            DSMGenerateRequestItem(
                                sequence="<mask>" * 50
                            )  # User sends mask tokens of desired length
                        ],
                    ),
                    input_filename_template=GENERATE_UNCONDITIONAL_INPUT,
                    expected_output_fixture=GENERATE_UNCONDITIONAL_OUTPUT_TPL,
                ),
                # Test Case 2: generate() with masked sequence (base models)
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=DSMGenerateRequest(
                        params=DSMGenerateRequestParams(
                            num_sequences=2,
                            temperature=0.8,
                            step_divisor=100,
                            remasking=DSMRemaskingStrategy.RANDOM,
                        ),
                        items=[
                            DSMGenerateRequestItem(
                                sequence="MKAAVDLK<mask><mask><mask>PFPSPDMECADVPLLTPSSKEMMSQALKATFSGFTKEQQRLGIPKDPRQWTETHVRDWVMWAVNEFSLKGVDFQKF"
                            )
                        ],
                    ),
                    input_filename_template=GENERATE_MASKED_INPUT,
                    expected_output_fixture=GENERATE_MASKED_OUTPUT_TPL,
                ),
                # Test Case 3: generate() with conditional generation (base models)
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=DSMGenerateRequest(
                        params=DSMGenerateRequestParams(
                            num_sequences=2,
                            temperature=0.9,
                            max_length=100,
                            step_divisor=100,
                            remasking=DSMRemaskingStrategy.RANDOM,
                        ),
                        items=[
                            DSMGenerateRequestItem(
                                sequence="MGTPLWALLGGPWRGTATYEDGTKVTLDYRYTRVSPDRLRADVTYTTPDGTTLEATVDLWKDANGVIRYHATYPDGTSADGTLTQLDADTLLATGTYDDGTKYTVTLTRVAPGSGWHHHHHH<eos>"
                                + "<mask>"
                                * 50  # BBF-14 target + <eos> + masked interactor
                            )
                        ],
                    ),
                    input_filename_template=GENERATE_CONDITIONAL_INPUT,
                    expected_output_fixture=GENERATE_CONDITIONAL_OUTPUT_TPL,
                ),
                # Test Case 4: encode() with mean pooling
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=DSMEncodeRequest(
                        params=DSMEncodeRequestParams(
                            include=[DSMEncodeIncludeOptions.MEAN],
                        ),
                        items=[DSMEncodeRequestItem(sequence=STANDARD_PROTEIN)],
                    ),
                    input_filename_template=ENCODE_MEAN_INPUT,
                    expected_output_fixture=ENCODE_MEAN_OUTPUT_TPL,
                ),
                # Test Case 5: encode() with per-residue embeddings
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=DSMEncodeRequest(
                        params=DSMEncodeRequestParams(
                            include=[
                                DSMEncodeIncludeOptions.MEAN,
                                DSMEncodeIncludeOptions.PER_RESIDUE,
                            ],
                        ),
                        items=[
                            DSMEncodeRequestItem(
                                sequence="MKAAVDLKTFPFPSPDMECADVPLLTPSSKEMMSQALKATFSGFTKEQQRLGIPKDPR"
                            )
                        ],
                    ),
                    input_filename_template=ENCODE_PER_RESIDUE_INPUT,
                    expected_output_fixture=ENCODE_PER_RESIDUE_OUTPUT_TPL,
                ),
                # Test Case 6: score() with log probabilities
                ActionTestCase(
                    action_name=ModelActions.SCORE,
                    input_fixture=DSMScoreRequest(
                        items=[
                            DSMScoreRequestItem(
                                sequence="MKAAVDLKTFPFPSPDMECADVPLLTPSSKEMMSQALKATFSGFTKEQQRLGIPKDPRQWTETHVRDWVMWAVNEFSLKGVDFQKF"
                            ),
                            DSMScoreRequestItem(sequence=STANDARD_PROTEIN),
                        ]
                    ),
                    input_filename_template=SCORE_INPUT,
                    expected_output_fixture=SCORE_OUTPUT_TPL,
                ),
            ],
        ),
        # PPI models (650m-ppi)
        VariantTestMapping(
            variant_config={"VARIANT": "ppi"},
            test_cases=[
                # Test Case 1: generate() with unconditional generation (PPI models - dual format)
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=DSMGenerateRequest(
                        params=DSMGenerateRequestParams(
                            num_sequences=3,
                            temperature=1.0,
                            max_length=100,
                            step_divisor=100,
                            remasking=DSMRemaskingStrategy.RANDOM,
                        ),
                        items=[
                            DSMGenerateRequestItem(
                                sequence="<mask>" * 50
                                + "<eos>"
                                + "<mask>"
                                * 50  # Dual unconditional: masked target + <eos> + masked interactor
                            )
                        ],
                    ),
                    input_filename_template=GENERATE_UNCONDITIONAL_INPUT,
                    expected_output_fixture=GENERATE_UNCONDITIONAL_OUTPUT_TPL,
                ),
                # Test Case 2: generate() with masked sequence (PPI models - dual format)
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=DSMGenerateRequest(
                        params=DSMGenerateRequestParams(
                            num_sequences=2,
                            temperature=0.8,
                            step_divisor=100,
                            remasking=DSMRemaskingStrategy.RANDOM,
                        ),
                        items=[
                            DSMGenerateRequestItem(
                                sequence="MKAAVDLK<mask><mask><mask>PFPSPDMECADVPLLTPSSKEMMSQALKATFSGFTKEQQRLGIPKDPRQWTETHVRDWVMWAVNEFSLKGVDFQKF<eos><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask><mask>"
                            )
                        ],
                    ),
                    input_filename_template=GENERATE_MASKED_INPUT,
                    expected_output_fixture=GENERATE_MASKED_OUTPUT_TPL,
                ),
                # Test Case 3: generate() with conditional generation (PPI models)
                ActionTestCase(
                    action_name=ModelActions.GENERATE,
                    input_fixture=DSMGenerateRequest(
                        params=DSMGenerateRequestParams(
                            num_sequences=2,
                            temperature=0.9,
                            max_length=100,
                            step_divisor=100,
                            remasking=DSMRemaskingStrategy.RANDOM,
                        ),
                        items=[
                            DSMGenerateRequestItem(
                                sequence="MGTPLWALLGGPWRGTATYEDGTKVTLDYRYTRVSPDRLRADVTYTTPDGTTLEATVDLWKDANGVIRYHATYPDGTSADGTLTQLDADTLLATGTYDDGTKYTVTLTRVAPGSGWHHHHHH<eos>"
                                + "<mask>"
                                * 50  # BBF-14 target + <eos> + masked interactor
                            )
                        ],
                    ),
                    input_filename_template=GENERATE_CONDITIONAL_INPUT,
                    expected_output_fixture=GENERATE_CONDITIONAL_OUTPUT_TPL,
                ),
                # Test Case 4: encode() with mean pooling
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=DSMEncodeRequest(
                        params=DSMEncodeRequestParams(
                            include=[DSMEncodeIncludeOptions.MEAN],
                        ),
                        items=[DSMEncodeRequestItem(sequence=STANDARD_PROTEIN)],
                    ),
                    input_filename_template=ENCODE_MEAN_INPUT,
                    expected_output_fixture=ENCODE_MEAN_OUTPUT_TPL,
                ),
                # Test Case 5: encode() with per-residue embeddings
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=DSMEncodeRequest(
                        params=DSMEncodeRequestParams(
                            include=[
                                DSMEncodeIncludeOptions.MEAN,
                                DSMEncodeIncludeOptions.PER_RESIDUE,
                            ],
                        ),
                        items=[
                            DSMEncodeRequestItem(
                                sequence="MKAAVDLKTFPFPSPDMECADVPLLTPSSKEMMSQALKATFSGFTKEQQRLGIPKDPR"
                            )
                        ],
                    ),
                    input_filename_template=ENCODE_PER_RESIDUE_INPUT,
                    expected_output_fixture=ENCODE_PER_RESIDUE_OUTPUT_TPL,
                ),
                # Test Case 6: score() with log probabilities
                ActionTestCase(
                    action_name=ModelActions.SCORE,
                    input_fixture=DSMScoreRequest(
                        items=[
                            DSMScoreRequestItem(
                                sequence="MKAAVDLKTFPFPSPDMECADVPLLTPSSKEMMSQALKATFSGFTKEQQRLGIPKDPRQWTETHVRDWVMWAVNEFSLKGVDFQKF"
                            ),
                            DSMScoreRequestItem(sequence=STANDARD_PROTEIN),
                        ]
                    ),
                    input_filename_template=SCORE_INPUT,
                    expected_output_fixture=SCORE_OUTPUT_TPL,
                ),
            ],
        ),
    ],
)


def generate() -> None:
    """Configures and runs the fixture generator"""
    generator = FixtureGenerator(fixture_generation_suite)
    generator.generate()


if __name__ == "__main__":
    generate()
