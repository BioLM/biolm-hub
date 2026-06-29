import requests

from models.boltzgen.config import MODEL_FAMILY
from models.boltzgen.schema import (
    BoltzGenBindingType,
    BoltzGenChainSelector,
    BoltzGenDesignParams,
    BoltzGenDesignRequest,
    BoltzGenDesignRequestItem,
    BoltzGenDesignSpec,
    BoltzGenEntity,
    BoltzGenFileEntity,
    BoltzGenLigandEntity,
    BoltzGenProteinEntity,
    BoltzGenProtocol,
    BoltzGenStructureGroup,
)
from models.commons.core.logging import get_logger
from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator

logger = get_logger(__name__)

# BoltzGen repository configuration for fetching example CIF/PDB files.
# This commit (3eddb5a) is the knowledge-graph snapshot used for sourcing test
# fixtures and is intentionally separate from the deployed code commit (617e549
# in helpers.py). The example files are stable across minor commits.
BOLTZGEN_REPO = "HannesStark/boltzgen"
BOLTZGEN_COMMIT = "3eddb5a3c73eb466c3e787cdfacf5c1d1693e1b5"
BOLTZGEN_BASE_URL = (
    f"https://raw.githubusercontent.com/{BOLTZGEN_REPO}/{BOLTZGEN_COMMIT}/example"
)


def fetch_structure_file(example_path: str, filename: str) -> str:
    """
    Fetch a CIF or PDB file from the boltzgen GitHub repository.

    Args:
        example_path: Path within the example directory (e.g., "hard_targets", "vanilla_peptide_with_target_binding_site")
        filename: Name of the structure file (e.g., "1g13.cif", "5cqg.cif")

    Returns:
        The file content as a string

    Raises:
        RuntimeError: If the file cannot be fetched
    """
    url = f"{BOLTZGEN_BASE_URL}/{example_path}/{filename}"

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        raise RuntimeError(
            f"Failed to fetch structure file from {url}: {e}\n"
            f"Make sure the file exists in the boltzgen repository."
        ) from e


def strip_water_from_cif(cif_content: str) -> str:
    """
    Remove water molecules (HOH) from CIF content using gemmi.

    Water molecules can cause SASA calculation failures in the analysis step
    when they have empty coordinates after refolding. Since water molecules
    aren't part of the design target, it's safe to remove them.

    Args:
        cif_content: Full CIF file content

    Returns:
        CIF content with water molecules removed
    """
    try:
        import gemmi

        doc = gemmi.cif.read_string(cif_content)
        block = doc[0]
        st = gemmi.make_structure_from_block(block)
        st.remove_waters()
        st.update_mmcif_block(block)
        return doc.as_string()
    except Exception:
        # Fallback: line-based filtering for environments without gemmi
        lines = cif_content.split("\n")
        filtered_lines = [line for line in lines if "HOH" not in line]
        return "\n".join(filtered_lines)


def get_cif_content(pdb_id: str, example_path: str, strip_water: bool = False) -> str:
    """
    Get CIF content for a specific PDB ID from boltzgen examples.

    Args:
        pdb_id: PDB ID (e.g., "1g13", "5cqg", "7eow")
        example_path: Path within the example directory
        strip_water: Whether to remove water molecules from the CIF

    Returns:
        Full CIF file content as string
    """
    filename = f"{pdb_id.lower()}.cif"
    content = fetch_structure_file(example_path, filename)
    if strip_water:
        content = strip_water_from_cif(content)
    return content


# Create TestSuite for fixture generation with programmatic inputs
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        # Single mapping that applies to ALL variants
        VariantTestMapping(
            variant_config={},  # Empty dict means applies to ALL variants
            test_cases=[
                # Test cases will be added by the generate() function
            ],
        )
    ],
)


def generate():
    """
    Configures and runs the fixture generator for multiple scenarios based on boltzgen examples.

    All test cases use minimal budgets (num_designs=3, budget=2) for cost-effective testing.
    This is sufficient to validate design diversity while keeping test costs low.
    """
    generator = FixtureGenerator(fixture_generation_suite)

    #############################################################################
    # PROTOCOL: peptide-anything
    # Design (cyclic) peptides or others to bind proteins
    #############################################################################

    # Example 1: cyclic_against_hiv_antibody_site/9d3d.yaml
    # Design a cyclic peptide (8-18 residues) to bind HIV antibody
    logger.info("Fetching 9d3d.cif from boltzgen repository...")
    cif_9d3d = get_cif_content("9d3d", "cyclic_against_hiv_antibody_site")

    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.GENERATE,
            input_fixture=BoltzGenDesignRequest(
                params=BoltzGenDesignParams(
                    protocol=BoltzGenProtocol.PEPTIDE_ANYTHING,
                    num_designs=3,
                    budget=2,
                ),
                items=[
                    BoltzGenDesignRequestItem(
                        entities=[
                            BoltzGenEntity(
                                file=BoltzGenFileEntity(
                                    cif=cif_9d3d,
                                    include=[
                                        BoltzGenChainSelector(id="A"),
                                        BoltzGenChainSelector(id="B"),
                                        BoltzGenChainSelector(id="C"),
                                    ],
                                    include_proximity=[
                                        {
                                            "chain": {
                                                "id": "G",
                                                "res_index": "106..118",
                                                "radius": 30,
                                            }
                                        }
                                    ],
                                    binding_types=[
                                        BoltzGenBindingType(
                                            chain="A", binding=[91, 128, 131]
                                        ),
                                        BoltzGenBindingType(
                                            chain="B", binding=[91, 128, 131]
                                        ),
                                        BoltzGenBindingType(
                                            chain="C", binding=[91, 128, 131]
                                        ),
                                    ],
                                )
                            ),
                            BoltzGenEntity(
                                protein=BoltzGenProteinEntity(
                                    id="E",
                                    sequence="8..18",
                                    cyclic=True,
                                )
                            ),
                        ],
                        constraints=None,
                    )
                ],
            ),
            input_filename_template="cyclic_hiv_9d3d_input.json",
            expected_output_fixture="cyclic_hiv_9d3d_expected_output.json",
        )
    )

    # Example 5: streptavidin_partially_flexible_target/cyclic.yaml
    # Design a cyclic peptide (8-18 residues) to bind streptavidin with partial flexibility
    logger.info("Fetching 1mk5.cif from boltzgen repository...")
    cif_1mk5 = get_cif_content("1mk5", "streptavidin_partially_flexible_target")

    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.GENERATE,
            input_fixture=BoltzGenDesignRequest(
                params=BoltzGenDesignParams(
                    protocol=BoltzGenProtocol.PEPTIDE_ANYTHING,
                    num_designs=3,
                    budget=2,
                ),
                items=[
                    BoltzGenDesignRequestItem(
                        entities=[
                            BoltzGenEntity(
                                protein=BoltzGenProteinEntity(
                                    id="C",
                                    sequence="8..18",
                                    cyclic=True,
                                )
                            ),
                            BoltzGenEntity(
                                file=BoltzGenFileEntity(
                                    cif=cif_1mk5,
                                    include=[BoltzGenChainSelector(id="A")],
                                    structure_groups=[
                                        BoltzGenStructureGroup(
                                            group={"id": "A"}, visibility=1
                                        ),
                                        BoltzGenStructureGroup(
                                            group={"id": "A", "res_index": "32..42"},
                                            visibility=0,
                                        ),
                                    ],
                                )
                            ),
                        ],
                        constraints=None,
                    )
                ],
            ),
            input_filename_template="streptavidin_cyclic_input.json",
            expected_output_fixture="streptavidin_cyclic_expected_output.json",
        )
    )

    #############################################################################
    # PROTOCOL: protein-small_molecule
    # Design proteins to bind small molecules
    #############################################################################

    # Example 6: protein_binding_small_molecule/chorismite.yaml
    # Design a protein (140-180 residues) to bind to small molecule TSA
    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.GENERATE,
            input_fixture=BoltzGenDesignRequest(
                params=BoltzGenDesignParams(
                    protocol=BoltzGenProtocol.PROTEIN_SMALL_MOLECULE,
                    num_designs=3,
                    budget=2,
                ),
                items=[
                    BoltzGenDesignRequestItem(
                        entities=[
                            BoltzGenEntity(
                                protein=BoltzGenProteinEntity(
                                    id="A",
                                    sequence="140..180",
                                )
                            ),
                            BoltzGenEntity(
                                ligand=BoltzGenLigandEntity(
                                    id="B",
                                    ccd="TSA",  # Chorismate synthase transition state analog
                                )
                            ),
                        ],
                        constraints=None,
                    )
                ],
            ),
            input_filename_template="protein_small_molecule_chorismite_input.json",
            expected_output_fixture="protein_small_molecule_chorismite_expected_output.json",
        )
    )

    #############################################################################
    # PROTOCOL: nanobody-anything
    # Design nanobodies (single-domain antibodies)
    #############################################################################

    # Example 7: nanobody_scaffolds/7eow.yaml (simplified version)
    # Design nanobody by redesigning CDR regions of chain B in 7eow.cif
    logger.info("Fetching 7eow.cif from boltzgen repository...")
    cif_7eow = get_cif_content("7eow", "nanobody_scaffolds", strip_water=True)

    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.GENERATE,
            input_fixture=BoltzGenDesignRequest(
                params=BoltzGenDesignParams(
                    protocol=BoltzGenProtocol.NANOBODY_ANYTHING,
                    num_designs=3,
                    budget=2,
                ),
                items=[
                    BoltzGenDesignRequestItem(
                        entities=[
                            BoltzGenEntity(
                                file=BoltzGenFileEntity(
                                    cif=cif_7eow,
                                    include=[
                                        BoltzGenChainSelector(id="A"),
                                        BoltzGenChainSelector(id="B"),
                                    ],
                                    design=[
                                        BoltzGenDesignSpec(
                                            chain="B",
                                            res_index="26..34,52..59,98..118",
                                        )
                                    ],
                                )
                            ),
                        ],
                        constraints=None,
                    )
                ],
            ),
            input_filename_template="nanobody_7eow_simple_input.json",
            expected_output_fixture="nanobody_7eow_simple_expected_output.json",
        )
    )

    # Example 8: hard_targets/1g13nano.yaml (simplified - single nanobody scaffold)
    # Design a nanobody to bind to chain A of 1g13
    logger.info("Fetching 1g13.cif from boltzgen repository...")
    cif_1g13 = get_cif_content("1g13", "vanilla_protein")
    logger.info("Fetching 7xl0.cif from boltzgen repository...")
    cif_7xl0 = get_cif_content("7xl0", "nanobody_scaffolds", strip_water=True)

    generator.add_test_case(
        ActionTestCase(
            action_name=ModelActions.GENERATE,
            input_fixture=BoltzGenDesignRequest(
                params=BoltzGenDesignParams(
                    protocol=BoltzGenProtocol.NANOBODY_ANYTHING,
                    num_designs=3,
                    budget=2,
                ),
                items=[
                    BoltzGenDesignRequestItem(
                        entities=[
                            BoltzGenEntity(
                                file=BoltzGenFileEntity(
                                    cif=cif_1g13,
                                    include=[BoltzGenChainSelector(id="A")],
                                )
                            ),
                            BoltzGenEntity(
                                file=BoltzGenFileEntity(
                                    cif=cif_7xl0,
                                    include=[BoltzGenChainSelector(id="B")],
                                    design=[
                                        BoltzGenDesignSpec(
                                            chain="B",
                                            res_index="26..34,52..59,98..115",
                                        )
                                    ],
                                )
                            ),
                        ],
                        constraints=None,
                    )
                ],
            ),
            input_filename_template="hard_target_1g13nano_input.json",
            expected_output_fixture="hard_target_1g13nano_expected_output.json",
        )
    )

    logger.info("=" * 80)
    logger.info(
        "Added %s test cases to fixture generation suite",
        len(fixture_generation_suite.variant_test_mappings[0].test_cases),
    )
    logger.info("=" * 80)

    generator.generate()


if __name__ == "__main__":
    generate()
