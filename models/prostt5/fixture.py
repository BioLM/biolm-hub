from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.commons.testing.shared_assets import STANDARD_PROTEIN
from models.prostt5.config import MODEL_FAMILY
from models.prostt5.schema import (
    ProstT5EncodeRequestAA,
    ProstT5EncodeRequestFold,
    ProstT5EncodeRequestItemAA,
    ProstT5EncodeRequestItemFold,
    ProstT5GenerateParamsAA,
    ProstT5GenerateRequestAA,
    ProstT5GenerateRequestItemAA,
)

# Test input/output filenames. Inputs are self-contained (inlined below), so
# generation needs no pre-existing R2 assets — the generator writes these
# inputs to R2 alongside the generated outputs.
AA_INPUT = "aa_input.json"
FOLD_INPUT = "fold_input.json"
AA_GENERATE_INPUT = "aa_generate_input.json"
AA_ENCODE_OUTPUT = "aa_encode_expected_output.json"
FOLD_ENCODE_OUTPUT = "fold_encode_expected_output.json"
# generate() has no golden-file comparison in test.py (a custom validator
# checks length/case instead of an exact diff), but the generator still
# writes the actual output somewhere so it can be inspected.
AA_GENERATE_OUTPUT = "aa_generate_expected_output.json"
FOLD_GENERATE_OUTPUT = "fold_generate_expected_output.json"

# Canonical 3Di structural-token sequence (Foldseek's lowercase alphabet),
# reused verbatim from the README's usage examples — already known-valid for
# this model (encode and generate both accept it, and it satisfies both the
# encode max length of 1000 and the generate max length of 512).
THREEDI_SEQUENCE = "dddahklqppddvvddddahhppllddddefgh"


def _build_fixture_generation_suite() -> TestSuite:
    """Build the fixture-generation suite for ProstT5's 4 variants.

    Inputs are inlined (self-contained), so importing this module never
    touches R2 or the network. ``FOLD_INPUT`` is intentionally shared between
    the encode/fold2AA and generate/fold2AA variants: it is built with the
    (stricter) Encode schema — which has no ``params`` field — so the
    resulting JSON validates against both ``ProstT5EncodeRequestFold`` and
    ``ProstT5GenerateRequestFold`` (whose ``params`` is optional), matching
    how models/prostt5/test.py reuses ``FOLD_INPUT`` for both request
    schemas.
    """
    aa_encode_request = ProstT5EncodeRequestAA(
        items=[ProstT5EncodeRequestItemAA(sequence=STANDARD_PROTEIN)]
    )
    fold_request = ProstT5EncodeRequestFold(
        items=[ProstT5EncodeRequestItemFold(sequence=THREEDI_SEQUENCE)]
    )
    aa_generate_request = ProstT5GenerateRequestAA(
        params=ProstT5GenerateParamsAA(
            temperature=1.2,
            top_p=0.95,
            num_samples=2,
            seed=42,
        ),
        items=[ProstT5GenerateRequestItemAA(sequence=STANDARD_PROTEIN)],
    )

    return TestSuite(
        model_family=MODEL_FAMILY,
        r2_fixture_subdir="models",
        variant_test_mappings=[
            # Encode, fold2AA direction (lowercase 3Di tokens -> embedding)
            VariantTestMapping(
                variant_config={
                    "MODEL_ACTION": "encode",
                    "MODEL_DIRECTION": "fold2AA",
                },
                test_cases=[
                    ActionTestCase(
                        action_name=ModelActions.ENCODE,
                        input_fixture=fold_request,
                        input_filename_template=FOLD_INPUT,
                        expected_output_fixture=FOLD_ENCODE_OUTPUT,
                        tolerances={"rel_tol": 1e-3, "cosine_distance_threshold": 0.02},
                    ),
                ],
            ),
            # Encode, AA2fold direction (uppercase amino acids -> embedding)
            VariantTestMapping(
                variant_config={
                    "MODEL_ACTION": "encode",
                    "MODEL_DIRECTION": "AA2fold",
                },
                test_cases=[
                    ActionTestCase(
                        action_name=ModelActions.ENCODE,
                        input_fixture=aa_encode_request,
                        input_filename_template=AA_INPUT,
                        expected_output_fixture=AA_ENCODE_OUTPUT,
                        tolerances={"rel_tol": 1e-3, "cosine_distance_threshold": 0.02},
                    ),
                ],
            ),
            # Generate, fold2AA direction (3Di -> amino acids / inverse folding).
            # Reuses the same FOLD_INPUT file written by the encode/fold2AA
            # mapping above (see docstring).
            VariantTestMapping(
                variant_config={
                    "MODEL_ACTION": "generate",
                    "MODEL_DIRECTION": "fold2AA",
                },
                test_cases=[
                    ActionTestCase(
                        action_name=ModelActions.GENERATE,
                        input_fixture=fold_request,
                        input_filename_template=FOLD_INPUT,
                        expected_output_fixture=FOLD_GENERATE_OUTPUT,
                    ),
                ],
            ),
            # Generate, AA2fold direction (amino acids -> 3Di translation)
            VariantTestMapping(
                variant_config={
                    "MODEL_ACTION": "generate",
                    "MODEL_DIRECTION": "AA2fold",
                },
                test_cases=[
                    ActionTestCase(
                        action_name=ModelActions.GENERATE,
                        input_fixture=aa_generate_request,
                        input_filename_template=AA_GENERATE_INPUT,
                        expected_output_fixture=AA_GENERATE_OUTPUT,
                    ),
                ],
            ),
        ],
    )


def generate():
    """Configures and runs the fixture generator for all 4 ProstT5 variants."""
    generator = FixtureGenerator(_build_fixture_generation_suite())
    generator.generate()


if __name__ == "__main__":
    generate()

# Run with: python models/prostt5/fixture.py
