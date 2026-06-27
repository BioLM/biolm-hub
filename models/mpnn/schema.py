import re
from functools import partial
from typing import Annotated, Literal, Optional, Union

from pydantic import (
    BeforeValidator,
    Field,
    model_validator,
)

from models.commons.data.structure_validator import validate_pdb
from models.commons.data.validator import validate_aa_unambiguous
from models.commons.model.base import ModelParams
from models.commons.model.pydantic import (
    EnhancedStringEnum,
    RequestModel,
    ResponseModel,
)
from models.commons.util.config import max_pdb_str_len

### MPNN Params


class MPNNParams(ModelParams):
    params_version = "v1"
    display_name = "MPNN"
    base_model_slug = "mpnn"
    log_identifier = "MPNN"
    batch_size = 1000
    num_batches = 48
    items_batch_size = 1
    sc_num_samples = 64
    sc_num_packs = 8
    sc_denoising_steps = 10
    max_sequence_len = 1024
    # appears to change the forward and is set to require separate load for LigandMPNN
    # and rather than have 2 deployments currently set to False. Could possibly be untangled as only affects forward pass
    ligand_mpnn_use_side_chain_context = False


class MPNNModelTypes(EnhancedStringEnum):
    PROTEIN = "protein"
    LIGAND = "ligand"
    SOLUBLE = "soluble"
    GLOBAL_LABEL_MEMBRANE = "global_label_membrane"
    PER_RESIDUE_LABEL_MEMBRANE = "per_residue_label_membrane"
    HYPER = "hyper"
    SIDE_CHAIN = "side_chain"


### MPNN Request


class MPNNGenerateParams(RequestModel):
    seed: Optional[int] = None
    temperature: float = 0.1
    fixed_residues: list[str] = Field(default_factory=partial(list, []))
    redesigned_residues: list[str] = Field(default_factory=partial(list, []))
    bias_AA: dict[str, float] = Field(default_factory=partial(dict, {}))
    bias_AA_per_residue: dict[str, dict[str, float]] = Field(
        default_factory=partial(dict, {})
    )
    omit_AA: str = ""
    omit_AA_per_residue: dict[str, str] = Field(default_factory=partial(dict, {}))
    symmetry_residues: list[list[str]] = Field(default_factory=partial(list, []))
    symmetry_weights: list[list[float]] = Field(default_factory=partial(list, []))
    homo_oligomer: bool = False
    chains_to_design: list[str] = Field(default_factory=partial(list, []))
    parse_these_chains_only: list[str] = Field(default_factory=partial(list, []))
    parse_atoms_with_zero_occupancy: bool = False

    number_of_batches: int = Field(1, ge=1, le=MPNNParams.num_batches)
    batch_size: int = Field(1, ge=1, le=MPNNParams.batch_size)

    # Side-chain (sc) model
    repack_everything: Optional[bool] = False
    pack_side_chains: Optional[bool] = False
    number_of_packs_per_design: Optional[int] = Field(
        1, ge=1, le=MPNNParams.sc_num_packs
    )
    sc_num_samples: Optional[int] = Field(16, ge=1, le=MPNNParams.sc_num_samples)
    sc_num_denoising_steps: Optional[int] = Field(
        3, ge=1, le=MPNNParams.sc_denoising_steps
    )
    force_hetatm: Optional[bool] = False
    pack_with_ligand_context: Optional[bool] = True

    # Hardcoded param defaults from argparser
    fasta_seq_separation: str = ":"
    file_ending: str = ""
    zero_indexed: int = 0

    # Unused or always set to None in the model
    pdb_path: None = None
    redesigned_residues_multi: None = None
    fixed_residues_multi: None = None
    bias_AA_per_residue_multi: None = None
    omit_AA_per_residue_multi: None = None
    save_stats: None = None
    verbose: bool = True
    ligand_mpnn_use_side_chain_context: None = None


class LigandMPNNGenerateParams(MPNNGenerateParams):
    ligand_mpnn_use_atom_context: Optional[bool] = True
    ligand_mpnn_cutoff_for_score: Optional[float] = 8.0


class GlobalMembraneMPNNGenerateParams(MPNNGenerateParams):
    global_transmembrane_label: Optional[Literal["membrane", "soluble"]] = "soluble"


class ResidueMembraneMPNNGenerateParams(MPNNGenerateParams):
    transmembrane_buried: Optional[list[str]] = None
    transmembrane_interface: Optional[list[str]] = None


class AllMPNNGenerateParams(MPNNGenerateParams):
    ligand_mpnn_use_atom_context: Optional[bool] = True
    ligand_mpnn_cutoff_for_score: Optional[float] = 8.0
    global_transmembrane_label: Optional[Literal["membrane", "soluble"]] = "soluble"
    transmembrane_buried: Optional[list[str]] = None
    transmembrane_interface: Optional[list[str]] = None


class MPNNGenerateRequestItem(RequestModel):
    pdb: Annotated[
        str,
        BeforeValidator(validate_pdb),
        Field(..., min_length=1, max_length=max_pdb_str_len),
    ]


def parse_pdb_string(pdb_string):
    """
    Parses a PDB string, returning a dict of chain -> count of unique residues,
    and a sorted list of the chain IDs found.
    """
    chain_residues = {}
    chains = set()

    for line in pdb_string.splitlines():
        if line.startswith("ATOM") or line.startswith("HETATM"):
            chain_id = line[21]
            res_num = line[22:26].strip()
            res_insertion = line[26].strip()  # Include insertion code if present
            residue_id = (res_num, res_insertion)

            if chain_id not in chain_residues:
                chain_residues[chain_id] = set()
            chain_residues[chain_id].add(residue_id)
            chains.add(chain_id)

    # Convert sets to counts
    chain_residue_counts = {
        chain: len(residues) for chain, residues in chain_residues.items()
    }
    chains_list = sorted(chains)  # Sorting to have a consistent order

    return chain_residue_counts, chains_list


def split_residue_string(s: str, field: str) -> tuple[str, int, Optional[str]]:
    """
    Match a residue specification where a sequence of letters (chain) is followed by
    a sequence of digits (position) and optionally another sequence of letters (insertion code).
    E.g. "A100", "B52A", "ChainA115B", etc.
    """
    match = re.match(r"([A-Za-z]+)(\d+)([A-Za-z]?)", s)
    if match:
        chain_id = match.group(1)
        residue_number = int(match.group(2))
        optional_insertion_code = match.group(3) if match.group(3) else None
        return chain_id, residue_number, optional_insertion_code
    else:
        raise ValueError(
            f"Residue specification format for {field} is not as expected: [ChainID][ResidueNumber][OptionalInsertionCode]"
        )


def validate_residue_lists(
    chain_counts: dict[str, int],
    chains: list[str],
    model_field: Optional[list[str]],
    model_field_name: str,
):
    """
    Validates that every residue string in model_field is actually present
    in the specified PDB (i.e., chain exists and residue number is within range).
    """
    if model_field:
        for i in model_field:
            chain_id, residue_number, _ = split_residue_string(i, model_field_name)
            if chain_id not in chains:
                raise ValueError(
                    f"Residue specification {i} has invalid chain id not "
                    f"detected in PDB chains: {chains}"
                )
            if not 1 <= int(residue_number) <= chain_counts[chain_id]:
                raise ValueError(
                    f"Residue specification {i} has invalid position greater than "
                    f"chain length: {chain_counts[chain_id]}"
                )


class MPNNGenerateRequest(RequestModel):
    params: AllMPNNGenerateParams
    items: Annotated[
        list[MPNNGenerateRequestItem],
        Field(min_length=1, max_length=1),
    ]

    @model_validator(mode="after")
    def validate_params(cls, instance):  # noqa: C901
        # FIXME(noqa: C901): Refactor to reduce complexity below the linter's threshold.

        params = instance.params
        items = instance.items

        if not items:
            raise ValueError("Items must be populated for params validation")

        # Validate top-level string fields containing AA
        if params.bias_AA:
            validate_aa_unambiguous("".join(params.bias_AA.keys()))

        if params.omit_AA:
            validate_aa_unambiguous(params.omit_AA)

        # Validate each provided PDB
        for item in items:
            chain_counts, chains = parse_pdb_string(item.pdb)

            # Validate chains_to_design
            if params.chains_to_design:
                for chain in params.chains_to_design:
                    if chain not in chains:
                        raise ValueError(
                            f"Chain {chain} in chains_to_design not found in PDB chains: {chains}"
                        )

            # Validate parse_these_chains_only
            if params.parse_these_chains_only:
                for chain in params.parse_these_chains_only:
                    if chain not in chains:
                        raise ValueError(
                            f"Chain {chain} in parse_these_chains_only not found in PDB chains: {chains}"
                        )

            # Validate residue lists
            validate_residue_lists(
                chain_counts, chains, params.fixed_residues, "fixed_residues"
            )
            validate_residue_lists(
                chain_counts, chains, params.redesigned_residues, "redesigned_residues"
            )
            validate_residue_lists(
                chain_counts,
                chains,
                params.transmembrane_buried,
                "transmembrane_buried",
            )
            validate_residue_lists(
                chain_counts,
                chains,
                params.transmembrane_interface,
                "transmembrane_interface",
            )

            # Validate bias_AA_per_residue
            if params.bias_AA_per_residue:
                for spec, aa_dict in params.bias_AA_per_residue.items():
                    chain_id, residue_number, _ = split_residue_string(
                        spec, "bias_AA_per_residue"
                    )
                    if chain_id not in chains:
                        raise ValueError(
                            f"Residue specification {spec} has an invalid chain ID not found in PDB chains: {chains}"
                        )
                    if not (1 <= residue_number <= chain_counts.get(chain_id, 0)):
                        raise ValueError(
                            f"Residue specification {spec} has invalid position "
                            f"greater than chain length ({chain_counts.get(chain_id, 0)})"
                        )
                    validate_aa_unambiguous("".join(aa_dict.keys()))

            # Validate omit_AA_per_residue
            if params.omit_AA_per_residue:
                for spec, omit_val in params.omit_AA_per_residue.items():
                    chain_id, residue_number, _ = split_residue_string(
                        spec, "omit_AA_per_residue"
                    )
                    if chain_id not in chains:
                        raise ValueError(
                            f"Residue specification {spec} has an invalid chain ID not found in PDB chains: {chains}"
                        )
                    if not (1 <= residue_number <= chain_counts.get(chain_id, 0)):
                        raise ValueError(
                            f"Residue specification {spec} has invalid position "
                            f"greater than chain length ({chain_counts.get(chain_id, 0)})"
                        )
                    validate_aa_unambiguous(omit_val)

            # Validate symmetry_residues
            if params.symmetry_residues:
                for pairs in params.symmetry_residues:
                    for spec in pairs:
                        chain_id, residue_number, _ = split_residue_string(
                            spec, "symmetry_residues"
                        )
                        if chain_id not in chains:
                            raise ValueError(
                                f"Residue specification {spec} has an invalid chain ID not found in PDB chains: {chains}"
                            )
                        if not (1 <= residue_number <= chain_counts.get(chain_id, 0)):
                            raise ValueError(
                                f"Residue specification {spec} has invalid position "
                                f"greater than chain length ({chain_counts.get(chain_id, 0)})"
                            )

            # Ensure symmetry_residues and symmetry_weights match
            if params.symmetry_residues and params.symmetry_weights:
                for sr_list, sw_list in zip(
                    params.symmetry_residues, params.symmetry_weights, strict=False
                ):
                    if len(sr_list) != len(sw_list):
                        raise ValueError(
                            f"Mismatch: symmetry_residues {sr_list} and symmetry_weights {sw_list} do not appear to match."
                        )

        return instance


class LigandMPNNGenerateRequest(MPNNGenerateRequest):
    params: LigandMPNNGenerateParams
    items: Annotated[
        list[MPNNGenerateRequestItem],
        Field(min_length=1, max_length=MPNNParams.items_batch_size),
    ]


class GlobalMembraneMPNNGenerateRequest(MPNNGenerateRequest):
    params: GlobalMembraneMPNNGenerateParams
    items: Annotated[
        list[MPNNGenerateRequestItem],
        Field(min_length=1, max_length=MPNNParams.items_batch_size),
    ]


class ResidueMembraneMPNNGenerateRequest(MPNNGenerateRequest):
    params: ResidueMembraneMPNNGenerateParams
    items: Annotated[
        list[MPNNGenerateRequestItem],
        Field(min_length=1, max_length=MPNNParams.items_batch_size),
    ]

    @model_validator(mode="after")
    def validate_membrane_params(cls, instance):
        params = instance.params
        items = instance.items

        if not items:
            raise ValueError("Items must be populated for membrane params validation")

        for item in items:
            chain_counts, chains = parse_pdb_string(item.pdb)

            validate_residue_lists(
                chain_counts,
                chains,
                params.transmembrane_buried,
                "transmembrane_buried",
            )
            validate_residue_lists(
                chain_counts,
                chains,
                params.transmembrane_interface,
                "transmembrane_interface",
            )

        return instance


### MPNN Response

FloatLike = Annotated[float, BeforeValidator(lambda v: float(v))]


class MPNNGenerateResponseItem(RequestModel):
    sequence: str
    pdb: str
    overall_confidence: FloatLike
    ligand_confidence: FloatLike
    seq_rec: FloatLike
    log_probs: list[list[float]]
    sampling_probs: list[list[float]]


class MPNNSCGenerateResponseItem(MPNNGenerateResponseItem):
    pdb_packed: dict[str, str]


class MPNNGenerateResponse(ResponseModel):
    results: list[Union[MPNNSCGenerateResponseItem, MPNNGenerateResponseItem]]
