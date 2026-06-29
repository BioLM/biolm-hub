from typing import Optional

from models.boltzgen.schema import BoltzGenPipelineStep
from models.commons.core.logging import get_logger

logger = get_logger(__name__)

# Amino acid 3-letter to 1-letter code mapping (used in CIF sequence extraction)
THREE_TO_ONE = {
    "ALA": "A",
    "ARG": "R",
    "ASN": "N",
    "ASP": "D",
    "CYS": "C",
    "GLN": "Q",
    "GLU": "E",
    "GLY": "G",
    "HIS": "H",
    "ILE": "I",
    "LEU": "L",
    "LYS": "K",
    "MET": "M",
    "PHE": "F",
    "PRO": "P",
    "SER": "S",
    "THR": "T",
    "TRP": "W",
    "TYR": "Y",
    "VAL": "V",
}

# BoltzGen repository configuration
BOLTZGEN_REPO_URL = "https://github.com/HannesStark/boltzgen.git"
BOLTZGEN_COMMIT = "617e549edf70787d899f47bc39e3746d8f10ffff"

# Default 7-stage pipeline when no explicit steps are requested
DEFAULT_PIPELINE_STEPS = [
    BoltzGenPipelineStep.DESIGN,
    BoltzGenPipelineStep.INVERSE_FOLDING,
    BoltzGenPipelineStep.FOLDING,
    BoltzGenPipelineStep.DESIGN_FOLDING,
    BoltzGenPipelineStep.AFFINITY,
    BoltzGenPipelineStep.ANALYSIS,
    BoltzGenPipelineStep.FILTERING,
]


def _chain_dict(chain) -> dict:
    """Normalize a chain field to ``{"id": chain}`` if it's a plain string."""
    return {"id": chain} if isinstance(chain, str) else chain


def convert_chain_selectors(selectors) -> list[dict]:
    """Convert a list of ChainSelector objects to boltzgen YAML format.

    Result format: ``[{"chain": {"id": "A", "res_index": ...}}, ...]``
    """
    result = []
    for sel in selectors:
        entry = {"chain": {"id": sel.id}}
        if sel.res_index is not None:
            entry["chain"]["res_index"] = sel.res_index
        result.append(entry)
    return result


def convert_design_specs(specs) -> list[dict]:
    """Convert a list of DesignSpec objects to boltzgen YAML format.

    Result format: ``[{"chain": {"id": "B"}, "res_index": "26..34"}, ...]``
    """
    result = []
    for ds in specs:
        entry: dict = {"chain": _chain_dict(ds.chain)}
        if ds.res_index is not None:
            entry["res_index"] = ds.res_index
        result.append(entry)
    return result


def convert_ss_specs(specs) -> list[dict]:
    """Convert a list of SecondaryStructureSpec objects to boltzgen YAML format.

    Result format: ``[{"chain": {"id": "A"}, "loop": 1, "helix": "2..3"}, ...]``
    """
    result = []
    for ss in specs:
        entry: dict = {"chain": _chain_dict(ss.chain)}
        if ss.loop is not None:
            entry["loop"] = ss.loop
        if ss.helix is not None:
            entry["helix"] = ss.helix
        if ss.sheet is not None:
            entry["sheet"] = ss.sheet
        result.append(entry)
    return result


def convert_binding_types(binding_types) -> list[dict] | str:
    """Convert binding_types to the dict format expected by boltzgen YAML.

    Handles both string shorthand (e.g. "all") and list-of-BindingType objects.
    """
    if isinstance(binding_types, str):
        return binding_types
    binding_list = []
    for bt in binding_types:
        bt_dict: dict = {"chain": _chain_dict(bt.chain)}
        if bt.binding is not None:
            bt_dict["binding"] = bt.binding
        if bt.not_binding is not None:
            bt_dict["not_binding"] = bt.not_binding
        binding_list.append(bt_dict)
    return binding_list


def extract_sequence_from_cif(cif_content: str) -> Optional[str]:  # noqa: C901
    """Extract amino-acid sequence from CIF file content using gemmi.

    Tries three strategies in order:
    1. ``_entity_poly.pdbx_seq_one_letter_code`` (most reliable)
    2. ``_entity_poly_seq.mon_id`` (fallback)
    3. ``_atom_site`` records (last resort)
    """
    try:
        import gemmi

        cif_doc = gemmi.cif.read_string(cif_content)
        if len(cif_doc) == 0:
            return None

        block = cif_doc[0]

        # Strategy 1: _entity_poly.pdbx_seq_one_letter_code
        entity_poly = block.find("_entity_poly.", ["pdbx_seq_one_letter_code"])
        if entity_poly:
            for row in entity_poly:
                if len(row) > 0:
                    seq = row[0].strip()
                    seq = (
                        seq.replace(";", "").replace("\n", "").replace(" ", "").strip()
                    )
                    if seq and len(seq) > 0:
                        return seq

        # Strategy 2: _entity_poly_seq (mon_id column)
        entity_poly_seq = block.find("_entity_poly_seq.", ["mon_id"])
        if entity_poly_seq:
            residues = []
            for row in entity_poly_seq:
                if len(row) > 0:
                    mon_id = row[0].strip()
                    if mon_id:
                        residues.append(mon_id)
            if residues:
                seq = "".join([THREE_TO_ONE.get(res, "X") for res in residues])
                if seq:
                    return seq

        # Strategy 3: atom_site records (less reliable)
        atom_site = block.find(
            "_atom_site.", ["label_comp_id", "label_asym_id", "label_seq_id"]
        )
        if atom_site:
            chains: dict[str, dict[str, str]] = {}
            for row in atom_site:
                if len(row) >= 3:
                    comp_id = row[0].strip()
                    chain_id = row[1].strip()
                    seq_id = row[2].strip()
                    if chain_id not in chains:
                        chains[chain_id] = {}
                    if seq_id not in chains[chain_id]:
                        chains[chain_id][seq_id] = comp_id

            if chains:
                # Prefer non-A chain (designed chain, usually B)
                for chain_id in sorted(chains.keys()):
                    if chain_id and chain_id != "A":
                        seq_ids = sorted(
                            chains[chain_id].keys(),
                            key=lambda x: int(x) if x.isdigit() else 0,
                        )
                        seq = "".join(
                            [
                                THREE_TO_ONE.get(chains[chain_id][sid], "X")
                                for sid in seq_ids
                            ]
                        )
                        if seq:
                            return seq
                # Fallback to A chain
                if "A" in chains:
                    seq_ids = sorted(
                        chains["A"].keys(),
                        key=lambda x: int(x) if x.isdigit() else 0,
                    )
                    seq = "".join(
                        [THREE_TO_ONE.get(chains["A"][sid], "X") for sid in seq_ids]
                    )
                    if seq:
                        return seq

        return None
    except Exception as e:
        logger.warning("Failed to extract sequence from CIF: %s", e, exc_info=True)
        return None
