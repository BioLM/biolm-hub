from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.msa_transformer.config import MODEL_FAMILY
from models.msa_transformer.schema import (
    MSATransformerEncodeIncludeOptions,
    MSATransformerEncodeRequest,
    MSATransformerEncodeRequestItem,
    MSATransformerEncodeRequestParams,
)

# Fixture filenames - used by both fixture generation and tests
SINGLE_MSA_INPUT = "single_msa_input.json"
SINGLE_MSA_ENCODE_OUTPUT = "single_msa_encode_expected_output.json"
BATCH_MSA_INPUT = "batch_msa_input.json"
BATCH_MSA_ENCODE_OUTPUT = "batch_msa_encode_expected_output.json"
# Additional fixtures to test row_attention and per_token outputs
ROW_ATTENTION_INPUT = "row_attention_input.json"
ROW_ATTENTION_OUTPUT = "row_attention_encode_expected_output.json"
PER_TOKEN_INPUT = "per_token_input.json"
PER_TOKEN_OUTPUT = "per_token_encode_expected_output.json"

# Define input fixtures programmatically as Pydantic objects
# Single MSA test case - small MSA with 5 sequences
single_msa_request = MSATransformerEncodeRequest(
    params=MSATransformerEncodeRequestParams(
        repr_layers=[-1],
        include=[
            MSATransformerEncodeIncludeOptions.MEAN,
            MSATransformerEncodeIncludeOptions.CONTACTS,
        ],
    ),
    items=[
        MSATransformerEncodeRequestItem(
            msa=[
                # Query sequence (first)
                "MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVL",
                # Aligned homologs with some variation
                "MKAVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVL",
                "MKTVRQERLKSIIRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVL",
                "MKTVRQERLKSIVRILERSKEPVSGAQLAEE-SVSRQVIVQDIAYLRSLGYNIVATPRGYVL",
                "MKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLG.NIVATPRGYVL",
            ]
        )
    ],
)

# Batch MSA test case - two MSAs
batch_msa_request = MSATransformerEncodeRequest(
    params=MSATransformerEncodeRequestParams(
        repr_layers=[-1],
        include=[MSATransformerEncodeIncludeOptions.MEAN],
    ),
    items=[
        # First MSA
        MSATransformerEncodeRequestItem(
            msa=[
                "MKTVRQERLKSIVRILERSKEPVSGAQLAE",
                "MKAVRQERLKSIVRILERSKEPVSGAQLAE",
                "MKTVRQERLKSIIRILERSKEPVSGAQLAE",
            ]
        ),
        # Second MSA
        MSATransformerEncodeRequestItem(
            msa=[
                "GVQVETISPGDGRTFPKRGQTCVVHYTGML",
                "GVQVETISPGDGRTFPKRGQTCVVHYTGML",
                "GVQVETISPGDGRTFPKRGQTCVIHYTGML",
            ]
        ),
    ],
)

# Row attention test case - small MSA to keep attention matrices manageable
row_attention_request = MSATransformerEncodeRequest(
    params=MSATransformerEncodeRequestParams(
        repr_layers=[-1],
        include=[MSATransformerEncodeIncludeOptions.ROW_ATTENTION],
    ),
    items=[
        MSATransformerEncodeRequestItem(
            msa=[
                "MKTVRQERLKSIVRILERSKEPVSG",  # 25 residues - keep attention small
                "MKAVRQERLKSIVRILERSKEPVSG",
                "MKTVRQERLKSIIRILERSKEPVSG",
            ]
        )
    ],
)

# Per-token embeddings test case - small sequence to keep output manageable
per_token_request = MSATransformerEncodeRequest(
    params=MSATransformerEncodeRequestParams(
        repr_layers=[-1],
        include=[MSATransformerEncodeIncludeOptions.PER_TOKEN],
    ),
    items=[
        MSATransformerEncodeRequestItem(
            msa=[
                "MKTVRQERLKSIVRILERSKEPVSG",  # 25 residues
                "MKAVRQERLKSIVRILERSKEPVSG",
                "MKTVRQERLKSIIRILERSKEPVSG",
            ]
        )
    ],
)

# TestSuite for fixture generation
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={},  # Single variant - empty config matches all
            test_cases=[
                # Test Case 1: Single MSA encode with contacts
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=single_msa_request,
                    input_filename_template=SINGLE_MSA_INPUT,
                    expected_output_fixture=SINGLE_MSA_ENCODE_OUTPUT,
                ),
                # Test Case 2: Batch MSA encode
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=batch_msa_request,
                    input_filename_template=BATCH_MSA_INPUT,
                    expected_output_fixture=BATCH_MSA_ENCODE_OUTPUT,
                ),
                # Test Case 3: Row attention output
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=row_attention_request,
                    input_filename_template=ROW_ATTENTION_INPUT,
                    expected_output_fixture=ROW_ATTENTION_OUTPUT,
                ),
                # Test Case 4: Per-token embeddings output
                ActionTestCase(
                    action_name=ModelActions.ENCODE,
                    input_fixture=per_token_request,
                    input_filename_template=PER_TOKEN_INPUT,
                    expected_output_fixture=PER_TOKEN_OUTPUT,
                ),
            ],
        )
    ],
)


def generate() -> None:
    """Configures and runs the fixture generator for MSA Transformer.

    This will:
    1. Upload input fixtures (Pydantic objects) to R2
    2. Run the model to generate golden outputs
    3. Upload outputs to R2
    """
    generator = FixtureGenerator(fixture_generation_suite)
    generator.generate()


if __name__ == "__main__":
    generate()

# Run with: python models/msa_transformer/fixture.py
