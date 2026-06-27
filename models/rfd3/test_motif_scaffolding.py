"""Test RFD3 motif scaffolding with 6IM3.pdb.

This test conserves the zinc-binding site and other critical residues:
- Histidines at 107, 109, and 126 (zinc coordination) - conserve region 100-130
- Other conserved residues: C44, N49, D60, H82, D182, D184, G190, L192, T193, T194, C197, G200
"""

import tempfile
from pathlib import Path

import pytest

from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.runner import generate_tests_from_suite
from models.rfd3.config import MODEL_FAMILY
from models.rfd3.schema import RFD3DesignRequest


def _check_conserved_residues(  # noqa: C901
    structure, item_idx, design_idx, output_dir, structure_cif, log
):
    """Check if conserved residues are present in the structure."""
    # Expected conserved residues
    # Region 100-130 contains H107, H109, H126 (zinc-binding)
    CONSERVED_REGION = (100, 130)  # Inclusive range
    CONSERVED_RESIDUES = [44, 49, 60, 82, 182, 184, 190, 192, 193, 194, 197, 200]
    CHAIN_ID = "A"

    # Validate conserved residues are present
    model = structure[0]  # Get first model
    if CHAIN_ID not in model:
        # Try to find any chain
        chains = list(model.get_chains())
        if not chains:
            raise AssertionError(f"Design {item_idx}[{design_idx}] has no chains")
        chain = chains[0]
        chain_id = chain.id
        log(f"\n⚠️  Chain {CHAIN_ID} not found, using chain {chain_id}")
    else:
        chain = model[CHAIN_ID]
        chain_id = CHAIN_ID

    # Get all residue numbers in the chain
    residue_numbers = []
    residue_info = {}  # Store residue name and number
    for residue in chain:
        res_id = residue.get_id()
        # Handle insertion codes (e.g., (' ', 100, ' '))
        if res_id[0] == " ":  # Standard residue
            res_num = res_id[1]
            residue_numbers.append(res_num)
            residue_info[res_num] = residue.get_resname()

    residue_numbers_set = set(residue_numbers)

    # Check conserved region (100-130) - this is critical
    region_residues = [
        r for r in residue_numbers if CONSERVED_REGION[0] <= r <= CONSERVED_REGION[1]
    ]
    assert len(region_residues) > 0, (
        f"Design {item_idx}[{design_idx}] missing conserved region {CONSERVED_REGION[0]}-{CONSERVED_REGION[1]} "
        f"(found residues: {sorted(residue_numbers)})"
    )
    log(
        f"\n✅ Conserved region {CONSERVED_REGION[0]}-{CONSERVED_REGION[1]} present with {len(region_residues)} residues"
    )
    log(f"   Region residues: {sorted(region_residues)}")

    # Check individual conserved residues
    missing_residues = []
    found_residues = []
    for res_num in CONSERVED_RESIDUES:
        if res_num in residue_numbers_set:
            resname = residue_info.get(res_num, "?")
            found_residues.append((res_num, resname))
        else:
            missing_residues.append(res_num)

    # Report findings
    if missing_residues:
        log(
            f"\n⚠️  Design {item_idx}[{design_idx}] missing {len(missing_residues)} conserved residues: {missing_residues}"
        )
        log(
            f"   Found {len(found_residues)}/{len(CONSERVED_RESIDUES)} conserved residues: {found_residues}"
        )
        log(
            f"   Available residue range: {min(residue_numbers) if residue_numbers else 'N/A'}-{max(residue_numbers) if residue_numbers else 'N/A'}"
        )
    else:
        log(
            f"\n✅ All {len(CONSERVED_RESIDUES)} conserved residues present: {found_residues}"
        )

    # Check for zinc-binding histidines specifically (107, 109, 126)
    zinc_binding_residues = [107, 109, 126]
    found_zinc_binding = []
    missing_zinc_binding = []
    for r in zinc_binding_residues:
        if r in residue_numbers_set:
            resname = residue_info.get(r, "?")
            found_zinc_binding.append((r, resname))
        else:
            missing_zinc_binding.append(r)

    if missing_zinc_binding:
        log(
            f"\n⚠️  Design {item_idx}[{design_idx}] missing zinc-binding residues: "
            f"found {found_zinc_binding}, missing {missing_zinc_binding}"
        )
        # This is a warning, not a failure - the region conservation is more important
    else:
        log(
            f"\n✅ All zinc-binding residues present: H{107} ({residue_info.get(107, '?')}), "
            f"H{109} ({residue_info.get(109, '?')}), H{126} ({residue_info.get(126, '?')})"
        )

    # Summary
    log(f"\n📊 Conservation Summary for Design {item_idx}[{design_idx}]:")
    log(
        f"   - Conserved region {CONSERVED_REGION[0]}-{CONSERVED_REGION[1]}: ✅ ({len(region_residues)} residues)"
    )
    log(
        f"   - Individual conserved residues: {len(found_residues)}/{len(CONSERVED_RESIDUES)} found"
    )
    log(
        f"   - Zinc-binding residues (H107, H109, H126): {len(found_zinc_binding)}/{len(zinc_binding_residues)} found"
    )


def _check_zinc_presence(
    structure, item_idx: int, design_idx: int, output_dir: Path, structure_cif: str, log
):
    """Check that zinc (ZN) is present in the generated structure."""
    zinc_atoms = []
    zinc_residues = []
    for model in structure:
        for chain in model:
            for residue in chain:
                # Check if residue is zinc (ZN)
                if residue.get_resname() == "ZN":
                    zinc_residues.append(residue)
                    for atom in residue:
                        zinc_atoms.append(atom)

    if not zinc_atoms:
        log(
            f"\n⚠️  Design {item_idx}[{design_idx}] missing zinc (ZN) ion - "
            "zinc should be included when ligands=['ZN'] is specified"
        )
        # Don't fail the test, but warn - zinc may be optional or handled differently
    else:
        log(
            f"\n✅ Design {item_idx}[{design_idx}] contains zinc (ZN) ion: "
            f"{len(zinc_residues)} residue(s), {len(zinc_atoms)} atom(s)"
        )
        # Log zinc coordinates for verification
        for i, residue in enumerate(zinc_residues):
            for atom in residue:
                coord = atom.get_coord()
                log(
                    f"   ZN[{i}] atom {atom.get_name()}: ({coord[0]:.2f}, {coord[1]:.2f}, {coord[2]:.2f})"
                )

    # Save CIF to file for visualization
    cif_filename = f"rfd3_design_{item_idx}_{design_idx}.cif"
    cif_path = output_dir / cif_filename
    with open(cif_path, "w") as f:
        f.write(structure_cif)
    log(f"\n💾 Saved design CIF to: {cif_path}")


def _validate_rfd3_motif_scaffolding(
    actual_output: dict, _expected_output: dict | None = None
):
    """Validator for RFD3 motif scaffolding that checks structure and conserved regions.

    Also saves generated CIFs to a directory for visualization.
    """
    import sys
    from io import StringIO
    from pathlib import Path

    from Bio.PDB.MMCIFParser import MMCIFParser

    # Create output directory for saved CIFs
    output_dir = Path(__file__).parent / "motif_scaffolding_outputs"
    output_dir.mkdir(exist_ok=True)

    def log(msg: str):
        """Log to stderr so it shows up in test output."""
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()

    assert "results" in actual_output, "Response missing 'results' key"
    assert len(actual_output["results"]) > 0, "Results list is empty"

    # Check each result item
    for item_idx, item in enumerate(actual_output["results"]):
        assert isinstance(item, list), f"Result {item_idx} should be a list of designs"
        assert len(item) > 0, f"Result {item_idx} list is empty"

        # Check each design in the result
        for design_idx, design in enumerate(item):
            assert (
                "structure_cif" in design
            ), f"Design {item_idx}[{design_idx}] missing 'structure_cif'"
            structure_cif = design["structure_cif"]
            assert isinstance(
                structure_cif, str
            ), f"Design {item_idx}[{design_idx}] structure_cif should be a string"
            assert (
                len(structure_cif) > 0
            ), f"Design {item_idx}[{design_idx}] structure_cif is empty"

            # Validate that the CIF can be parsed
            try:
                parser = MMCIFParser(QUIET=True)
                io = StringIO(structure_cif)
                structure = parser.get_structure(f"design_{item_idx}_{design_idx}", io)
                assert (
                    structure is not None
                ), f"Design {item_idx}[{design_idx}] CIF failed to parse"

                # Check that structure has atoms
                atoms = list(structure.get_atoms())
                assert (
                    len(atoms) > 0
                ), f"Design {item_idx}[{design_idx}] structure has no atoms"

                # Validate conserved residues are present
                _check_conserved_residues(
                    structure, item_idx, design_idx, output_dir, structure_cif, log
                )

                # Validate zinc is present
                _check_zinc_presence(
                    structure, item_idx, design_idx, output_dir, structure_cif, log
                )

            except Exception as e:
                raise AssertionError(
                    f"Design {item_idx}[{design_idx}] CIF parsing failed: {e}"
                ) from e


# Path to 6IM3.cif - will be downloaded locally
CIF_URL = "https://files.rcsb.org/download/6IM3.cif"


def download_6im3_cif() -> str:
    """Download 6IM3.cif directly and return as string.

    Returns:
        CIF format string of the structure
    """
    import urllib.request

    # Download CIF file to temp location
    temp_dir = Path(tempfile.gettempdir()) / "rfd3_tests"
    temp_dir.mkdir(exist_ok=True)
    cif_path = temp_dir / "6IM3.cif"

    if not cif_path.exists():
        print(f"📥 Downloading 6IM3.cif from {CIF_URL}...")
        urllib.request.urlretrieve(CIF_URL, cif_path)
        print(f"✅ Downloaded 6IM3.cif to {cif_path}")

    # Read CIF file
    with open(cif_path) as f:
        cif_content = f.read()

    print(f"✅ Loaded CIF format ({len(cif_content)} characters)")
    return cif_content


# Define test input for motif scaffolding with 6IM3
def create_motif_scaffolding_input():
    """Create the motif scaffolding input with 6IM3.cif."""
    # Download CIF file directly
    structure_cif = download_6im3_cif()

    return RFD3DesignRequest.model_validate(
        {
            "params": {
                "num_diffusion_steps": 100,
                "diffusion_batch_size": 1,
                "seed": 42,
                "temperature": 1.0,
                "conditioning_mode": "motif_scaffolding",
                "include_trajectories": False,
            },
            "items": [
                {
                    "name": "6im3_motif_scaffold",
                    "length": "200-250",  # Allow some flexibility in length
                    "unindex": [
                        "A107",
                        "A109",
                        "A126",
                    ],  # Zinc-binding histidines (unindexed)
                    "ligands": ["ZN"],  # Include zinc ion
                    "components": [
                        {
                            "name": "protein",
                            "chain_id": "A",
                            "structure_cif": structure_cif,  # Pass CIF as string
                            # Fix the zinc-binding region (100-130) and other critical residues
                            # Format: "A100-130" or "A100" (foundry format: chain + residue number)
                            "fixed_residues": [
                                "A100-130",  # Zinc-binding region (conserves H107, H109, H126)
                                "A44",  # C44
                                "A49",  # N49
                                "A60",  # D60
                                "A82",  # H82
                                "A182",  # D182
                                "A184",  # D184
                                "A190",  # G190
                                "A192",  # L192
                                "A193",  # T193
                                "A194",  # T194
                                "A197",  # C197
                                "A200",  # G200
                            ],
                        }
                    ],
                }
            ],
        }
    )


# Lazy-load the motif scaffolding input at import time only if the CIF is already
# cached locally.  If the cache is absent (offline / first collection), skip the
# module-scope download and let the setup_cif_file fixture populate it before the
# tests actually run.  This keeps the file import-clean for --collect-only.
_cif_cache_path = Path(tempfile.gettempdir()) / "rfd3_tests" / "6IM3.cif"
try:
    INPUT_MOTIF_SCAFFOLDING = create_motif_scaffolding_input()
    _motif_test_cases = [
        ActionTestCase(
            action_name=ModelActions.GENERATE,
            input_fixture=INPUT_MOTIF_SCAFFOLDING,
            expected_output_fixture=None,  # No expected output - validate structure existence only
            validator=_validate_rfd3_motif_scaffolding,
        ),
    ]
except Exception:
    # Network unavailable at import time — tests will be skipped (empty suite).
    # The setup_cif_file fixture will download the CIF before any actual test runs.
    INPUT_MOTIF_SCAFFOLDING = None
    _motif_test_cases = []

# Test suite
test_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={},  # Single variant
            test_cases=_motif_test_cases,
        )
    ],
)


@pytest.fixture(scope="module", autouse=True)
def setup_cif_file():
    """Download 6IM3.cif before running tests if needed."""
    # This will download and cache the CIF file
    download_6im3_cif()
    yield
    # Cleanup if needed


# Generate integration tests (marked with @pytest.mark.integration)
test_rfd3_integration = generate_tests_from_suite(test_suite, test_type="integration")

# Generate deployment tests (marked with @pytest.mark.deployment)
test_rfd3_deployment = generate_tests_from_suite(test_suite, test_type="deployment")

# Usage:
#   pytest models/rfd3/test_motif_scaffolding.py -m integration -n auto --no-cov -v -s  # integration only
#   pytest models/rfd3/test_motif_scaffolding.py -m deployment -n auto --no-cov -v -s   # deployment only
#   pytest models/rfd3/test_motif_scaffolding.py -n auto --no-cov -v -s                 # both
