from urllib.error import URLError
from urllib.request import urlopen

from models.commons.core.logging import get_logger
from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator
from models.esm_if1.config import MODEL_FAMILY
from models.esm_if1.schema import (
    ESMIF1GenerateParams,
    ESMIF1GenerateRequest,
    ESMIF1GenerateRequestItem,
)

logger = get_logger(__name__)

# Test input/output filenames. Inputs are self-contained (fetched inside
# generate() below), so generation needs no pre-existing R2 assets — the
# generator writes these inputs to R2 alongside the generated outputs.
GENERATE_INPUT = "generate_input.json"
GENERATE_OUTPUT = "generate_expected_output.json"


def _download_pdb(pdb_id: str) -> str:
    """Download a PDB-format structure file from RCSB and return it as text."""
    url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
    try:
        with urlopen(url, timeout=10) as response:
            return response.read().decode("utf-8")
    except URLError as e:
        raise ValueError(f"Failed to download PDB for {pdb_id}: {e}") from e


# TestSuite skeleton — the test case is built lazily inside generate() to avoid
# a module-scope network call (the RCSB PDB download) that would break
# --collect-only / plain imports of this module.
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={},  # Empty dict: applies to the single variant.
            test_cases=[],  # populated by generate()
        )
    ],
)


def generate():
    """Configures and runs the fixture generator for esm_if1 (single variant)."""
    # 1CRN: Crambin, a small (46-residue) single-chain protein — a fast, cheap
    # canonical structure for inverse folding (chain "A", matching the schema's
    # default `params.chain`).
    logger.info("Downloading PDB structure from RCSB...")
    pdb_1crn = _download_pdb("1CRN")
    logger.info("PDB structure downloaded successfully")

    fixture_generation_suite.variant_test_mappings[0].test_cases = [
        ActionTestCase(
            action_name=ModelActions.GENERATE,
            input_fixture=ESMIF1GenerateRequest(
                params=ESMIF1GenerateParams(
                    chain="A",
                    num_samples=2,
                    temperature=0.6,
                    seed=42,
                ),
                items=[
                    ESMIF1GenerateRequestItem(pdb=pdb_1crn),
                ],
            ),
            input_filename_template=GENERATE_INPUT,
            expected_output_fixture=GENERATE_OUTPUT,
            tolerances={
                "rel_tol": 0.5,
                "is_generated_seq": True,
            },
        ),
    ]

    generator = FixtureGenerator(fixture_generation_suite)
    generator.generate()


if __name__ == "__main__":
    generate()

# Run with: python models/esm_if1/fixture.py
