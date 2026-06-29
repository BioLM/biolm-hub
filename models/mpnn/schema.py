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
    seed: Optional[int] = Field(
        default=None,
        description="Random seed for reproducible sampling.",
    )
    temperature: float = Field(
        default=0.1,
        description="Sampling temperature; higher values increase diversity.",
    )
    fixed_residues: list[str] = Field(
        default_factory=partial(list, []),
        description=(
            "Residues to keep fixed (not redesigned), each as"
            " ChainId+Position (e.g., 'A10')."
        ),
    )
    redesigned_residues: list[str] = Field(
        default_factory=partial(list, []),
        description=(
            "Residues to redesign; all others remain fixed."
            " Each specified as ChainId+Position (e.g., 'A10')."
        ),
    )
    bias_AA: dict[str, float] = Field(
        default_factory=partial(dict, {}),
        description=(
            "Global log-odds bias per amino acid letter;"
            " positive values favor, negative values disfavor that amino acid."
        ),
    )
    bias_AA_per_residue: dict[str, dict[str, float]] = Field(
        default_factory=partial(dict, {}),
        description=(
            "Per-residue log-odds biases keyed by residue spec (e.g., 'A10'),"
            " mapping amino acid letter to bias value."
        ),
    )
    omit_AA: str = Field(
        default="",
        description=(
            "Amino acid letters to globally exclude from all designed positions"
            " (e.g., 'CM' omits Cys and Met)."
        ),
    )
    omit_AA_per_residue: dict[str, str] = Field(
        default_factory=partial(dict, {}),
        description=(
            "Per-residue amino acid exclusions keyed by residue spec (e.g., 'A10')"
            " with letters of amino acids to omit."
        ),
    )
    symmetry_residues: list[list[str]] = Field(
        default_factory=partial(list, []),
        description=(
            "Groups of residue specs that must receive the same amino acid"
            " identity for symmetric design."
        ),
    )
    symmetry_weights: list[list[float]] = Field(
        default_factory=partial(list, []),
        description=(
            "Log-odds weights for each symmetry group; each list must match the"
            " length of the corresponding symmetry_residues entry."
        ),
    )
    homo_oligomer: bool = Field(
        default=False,
        description=(
            "If true, automatically links equivalent positions across all chains"
            " for homo-oligomeric symmetry."
        ),
    )
    chains_to_design: list[str] = Field(
        default_factory=partial(list, []),
        description=(
            "Chain identifiers to redesign; if empty, all chains in the structure"
            " are designed."
        ),
    )
    parse_these_chains_only: list[str] = Field(
        default_factory=partial(list, []),
        description=(
            "If set, only these chains are parsed from the PDB;"
            " all other chains are ignored."
        ),
    )
    parse_atoms_with_zero_occupancy: bool = Field(
        default=False,
        description="If true, includes atoms with zero occupancy from the input PDB.",
    )

    number_of_batches: int = Field(
        1,
        ge=1,
        le=MPNNParams.num_batches,
        description=(
            "Number of sampling batches to run;"
            " total sequences generated = batch_size × number_of_batches."
        ),
    )
    batch_size: int = Field(
        1,
        ge=1,
        le=MPNNParams.batch_size,
        description="Number of sequences to generate per batch.",
    )

    # Side-chain (sc) model
    repack_everything: Optional[bool] = Field(
        default=False,
        description=(
            "If true, repacks all side chains (not just designed positions)"
            " when side-chain packing is enabled."
        ),
    )
    pack_side_chains: Optional[bool] = Field(
        default=False,
        description=(
            "If true, runs the side-chain packer to produce all-atom output"
            " alongside the backbone PDB."
        ),
    )
    number_of_packs_per_design: Optional[int] = Field(
        1,
        ge=1,
        le=MPNNParams.sc_num_packs,
        description=(
            "Number of side-chain packing attempts per design;"
            " results keyed by pack index in the response."
        ),
    )
    sc_num_samples: Optional[int] = Field(
        16,
        ge=1,
        le=MPNNParams.sc_num_samples,
        description="Number of diffusion samples per design used by the side-chain packer.",
    )
    sc_num_denoising_steps: Optional[int] = Field(
        3,
        ge=1,
        le=MPNNParams.sc_denoising_steps,
        description="Number of denoising steps performed by the side-chain packer per sample.",
    )
    force_hetatm: Optional[bool] = Field(
        default=False,
        description=(
            "If true, preserves the original HETATM record flags for non-protein"
            " (ligand/water) atoms in the packed output PDB."
        ),
    )
    pack_with_ligand_context: Optional[bool] = Field(
        default=True,
        description="If true, includes nearby ligand atoms when packing side chains.",
    )

    # Hardcoded param defaults from argparser
    fasta_seq_separation: str = Field(
        default=":",
        description="Separator character used between chains in multi-chain FASTA output.",
    )
    file_ending: str = Field(
        default="",
        description="Optional suffix appended to intermediate output file names; empty by default.",
    )
    zero_indexed: int = Field(
        default=0,
        description="Controls residue numbering in output files; 0 = one-based numbering (default).",
    )

    # Unused or always set to None in the model
    pdb_path: None = Field(
        default=None,
        description="Internal use only; always null in API requests.",
    )
    redesigned_residues_multi: None = Field(
        default=None,
        description="Internal use only; always null in API requests.",
    )
    fixed_residues_multi: None = Field(
        default=None,
        description="Internal use only; always null in API requests.",
    )
    bias_AA_per_residue_multi: None = Field(
        default=None,
        description="Internal use only; always null in API requests.",
    )
    omit_AA_per_residue_multi: None = Field(
        default=None,
        description="Internal use only; always null in API requests.",
    )
    save_stats: None = Field(
        default=None,
        description="Internal use only; always null in API requests.",
    )
    verbose: bool = Field(
        default=True,
        description="Internal verbosity flag; always true in server mode.",
    )
    ligand_mpnn_use_side_chain_context: None = Field(
        default=None,
        description="Internal use only; always null in API requests.",
    )


class LigandMPNNGenerateParams(MPNNGenerateParams):
    ligand_mpnn_use_atom_context: Optional[bool] = Field(
        default=True,
        description=(
            "If true, conditions sequence design on non-protein atom context"
            " (ligands, metals, nucleic acids)."
        ),
    )
    ligand_mpnn_cutoff_for_score: Optional[float] = Field(
        default=8.0,
        description="Distance cutoff in Ångströms for including ligand atoms in the confidence score.",
    )


class GlobalMembraneMPNNGenerateParams(MPNNGenerateParams):
    global_transmembrane_label: Optional[Literal["membrane", "soluble"]] = Field(
        default="soluble",
        description=(
            "Whole-protein membrane context label;"
            " 'membrane' for transmembrane proteins, 'soluble' otherwise."
        ),
    )


class ResidueMembraneMPNNGenerateParams(MPNNGenerateParams):
    transmembrane_buried: Optional[list[str]] = Field(
        default=None,
        description=(
            "Residue specs for positions buried in the membrane core,"
            " used to guide membrane-aware design."
        ),
    )
    transmembrane_interface: Optional[list[str]] = Field(
        default=None,
        description=(
            "Residue specs for positions at the membrane-water interface,"
            " used to guide membrane-aware design."
        ),
    )


class AllMPNNGenerateParams(MPNNGenerateParams):
    ligand_mpnn_use_atom_context: Optional[bool] = Field(
        default=True,
        description=(
            "If true, conditions sequence design on non-protein atom context"
            " (ligands, metals, nucleic acids)."
        ),
    )
    ligand_mpnn_cutoff_for_score: Optional[float] = Field(
        default=8.0,
        description="Distance cutoff in Ångströms for including ligand atoms in the confidence score.",
    )
    global_transmembrane_label: Optional[Literal["membrane", "soluble"]] = Field(
        default="soluble",
        description=(
            "Whole-protein membrane context label;"
            " 'membrane' for transmembrane proteins, 'soluble' otherwise."
        ),
    )
    transmembrane_buried: Optional[list[str]] = Field(
        default=None,
        description=(
            "Residue specs for positions buried in the membrane core,"
            " used to guide membrane-aware design."
        ),
    )
    transmembrane_interface: Optional[list[str]] = Field(
        default=None,
        description=(
            "Residue specs for positions at the membrane-water interface,"
            " used to guide membrane-aware design."
        ),
    )


class MPNNGenerateRequestItem(RequestModel):
    pdb: Annotated[
        str,
        BeforeValidator(validate_pdb),
        Field(
            ...,
            min_length=1,
            max_length=max_pdb_str_len,
            description="Input structure in PDB format.",
        ),
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
    params: AllMPNNGenerateParams = Field(
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: Annotated[
        list[MPNNGenerateRequestItem],
        Field(
            min_length=1,
            max_length=1,
            description="Batch of inputs to process in a single request. Accepts exactly 1 PDB structure.",
        ),
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
    params: LigandMPNNGenerateParams = Field(
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: Annotated[
        list[MPNNGenerateRequestItem],
        Field(
            min_length=1,
            max_length=MPNNParams.items_batch_size,
            description="Batch of inputs to process in a single request. Accepts exactly 1 PDB structure.",
        ),
    ]


class GlobalMembraneMPNNGenerateRequest(MPNNGenerateRequest):
    params: GlobalMembraneMPNNGenerateParams = Field(
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: Annotated[
        list[MPNNGenerateRequestItem],
        Field(
            min_length=1,
            max_length=MPNNParams.items_batch_size,
            description="Batch of inputs to process in a single request. Accepts exactly 1 PDB structure.",
        ),
    ]


class ResidueMembraneMPNNGenerateRequest(MPNNGenerateRequest):
    params: ResidueMembraneMPNNGenerateParams = Field(
        description="Optional parameters controlling this action (defaults are used when omitted).",
    )
    items: Annotated[
        list[MPNNGenerateRequestItem],
        Field(
            min_length=1,
            max_length=MPNNParams.items_batch_size,
            description="Batch of inputs to process in a single request. Accepts exactly 1 PDB structure.",
        ),
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
    sequence: str = Field(
        description=(
            "Designed amino acid sequence; chains are separated by ':'"
            " when multiple chains are present."
        ),
    )
    pdb: str = Field(
        description=(
            "Input backbone coordinates with the designed sequence threaded in,"
            " in PDB format."
        ),
    )
    overall_confidence: FloatLike = Field(
        description=(
            "Overall design confidence (0–1); computed as exp of negative"
            " cross-entropy loss over designed positions."
        ),
    )
    ligand_confidence: FloatLike = Field(
        description=(
            "Design confidence near ligand atoms (0–1);"
            " most informative for LigandMPNN variants."
        ),
    )
    seq_rec: FloatLike = Field(
        description=(
            "Sequence recovery relative to the native sequence (0–1);"
            " fraction of positions matching native."
        ),
    )
    log_probs: list[list[float]] = Field(
        description="Per-residue log probabilities over 21 amino acid types, in the model's canonical order.",
    )
    sampling_probs: list[list[float]] = Field(
        description="Per-residue sampling probabilities over 21 amino acid types, corresponding to log_probs.",
    )


class MPNNSCGenerateResponseItem(MPNNGenerateResponseItem):
    pdb_packed: dict[str, str] = Field(
        description=(
            "All-atom packed PDB structures after side-chain placement,"
            " keyed by pack index (e.g., 'packed_1')."
        ),
    )


class MPNNGenerateResponse(ResponseModel):
    results: list[Union[MPNNSCGenerateResponseItem, MPNNGenerateResponseItem]] = Field(
        description="Per-input results, returned in the same order as the request items.",
    )
