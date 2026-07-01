import copy
import json
import os.path
import random
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import torch
from prody import writePDB

from models.commons.core.logging import get_logger

from .LigandMPNN.data_utils import (
    alphabet,
    element_dict_rev,
    featurize,
    get_score,
    get_seq_rec,
    parse_PDB,
    restype_1to3,
    restype_int_to_str,
    restype_str_to_int,
    write_full_PDB,
)
from .LigandMPNN.model_utils import ProteinMPNN
from .LigandMPNN.sc_utils import Packer, pack_side_chains

logger = get_logger(__name__)

# ruff: disable


def load_mpnn(
    model_type: str,
    device: torch.device,
    checkpoint_path: Path,
    checkpoint_path_sc: Path,
    seed: int = 0,
    ligand_mpnn_use_side_chain_context: bool = False,
) -> tuple[ProteinMPNN, Packer, int]:
    """
    Loading function
    """

    if seed:
        seed = seed
    else:
        seed = int(np.random.randint(0, high=99999, size=1, dtype=int)[0])
    torch.manual_seed(seed)
    random.seed(seed)
    np.random.seed(seed)

    checkpoint = torch.load(
        checkpoint_path, map_location=device, weights_only=False  # R2 model store
    )
    if model_type == "ligand_mpnn":
        atom_context_num = checkpoint["atom_context_num"]
        ligand_mpnn_use_side_chain_context = ligand_mpnn_use_side_chain_context
        k_neighbors = checkpoint["num_edges"]
    else:
        atom_context_num = 1
        ligand_mpnn_use_side_chain_context = False
        k_neighbors = checkpoint["num_edges"]

    model = ProteinMPNN(
        node_features=128,
        edge_features=128,
        hidden_dim=128,
        num_encoder_layers=3,
        num_decoder_layers=3,
        k_neighbors=k_neighbors,
        device=device,
        atom_context_num=atom_context_num,
        model_type=model_type,
        ligand_mpnn_use_side_chain_context=ligand_mpnn_use_side_chain_context,
    )

    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()

    # condition if no sc
    model_sc = Packer(
        node_features=128,
        edge_features=128,
        num_positional_embeddings=16,
        num_chain_embeddings=16,
        num_rbf=16,
        hidden_dim=128,
        num_encoder_layers=3,
        num_decoder_layers=3,
        atom_context_num=16,
        lower_bound=0.0,
        upper_bound=20.0,
        top_k=32,
        dropout=0.0,
        augment_eps=0.0,
        atom37_order=False,
        device=device,
        num_mix=3,
    )

    checkpoint_sc = torch.load(
        checkpoint_path_sc, map_location=device, weights_only=False  # R2 model store
    )
    model_sc.load_state_dict(checkpoint_sc["model_state_dict"])
    model_sc.to(device)
    model_sc.eval()

    return model, model_sc, atom_context_num


def infer(  # noqa: C901
    model: ProteinMPNN, model_sc: Packer, atom_context_num: int, args: SimpleNamespace
) -> list[dict[str, Any]]:
    """
    Inference function
    """

    device = torch.device("cuda" if (torch.cuda.is_available()) else "cpu")
    folder_for_outputs = args.out_folder
    base_folder = folder_for_outputs

    if os.path.exists(base_folder + "backbones"):
        shutil.rmtree(base_folder + "backbones")
    if os.path.exists(base_folder + "seqs"):
        shutil.rmtree(base_folder + "seqs")
    if os.path.exists(base_folder + "packed"):
        shutil.rmtree(base_folder + "packed")

    if base_folder[-1] != "/":
        base_folder = base_folder + "/"
    if not os.path.exists(base_folder):
        os.makedirs(base_folder, exist_ok=True)
    if not os.path.exists(base_folder + "seqs"):
        os.makedirs(base_folder + "seqs", exist_ok=True)
    if not os.path.exists(base_folder + "backbones"):
        os.makedirs(base_folder + "backbones", exist_ok=True)
    if not os.path.exists(base_folder + "packed"):
        os.makedirs(base_folder + "packed", exist_ok=True)
    if args.save_stats:
        if not os.path.exists(base_folder + "stats"):
            os.makedirs(base_folder + "stats", exist_ok=True)

    if args.pdb_path_multi:
        pdb_paths = args.pdb_path_multi
    else:
        pdb_paths = [args.pdb_path]

    if args.fixed_residues_multi:
        with open(args.fixed_residues_multi) as fh:
            fixed_residues_multi = json.load(fh)
    else:
        fixed_residues = args.fixed_residues
        fixed_residues_multi = {}
        for pdb in pdb_paths:
            fixed_residues_multi[pdb] = fixed_residues

    if args.redesigned_residues_multi:
        with open(args.redesigned_residues_multi) as fh:
            redesigned_residues_multi = json.load(fh)
    else:
        redesigned_residues = args.redesigned_residues
        redesigned_residues_multi = {}
        for pdb in pdb_paths:
            redesigned_residues_multi[pdb] = redesigned_residues

    bias_AA = torch.zeros([21], device=device, dtype=torch.float32)
    if args.bias_AA:
        for AA, value in args.bias_AA.items():
            bias_AA[restype_str_to_int[AA]] = value

    if args.bias_AA_per_residue_multi:
        with open(args.bias_AA_per_residue_multi) as fh:
            bias_AA_per_residue_multi = json.load(
                fh
            )  # {"pdb_path" : {"A12": {"G": 1.1}}}
    else:
        if args.bias_AA_per_residue:
            bias_AA_per_residue = args.bias_AA_per_residue  # {"A12": {"G": 1.1}}
            bias_AA_per_residue_multi = {}
            for pdb in pdb_paths:
                bias_AA_per_residue_multi[pdb] = bias_AA_per_residue

    if args.omit_AA_per_residue_multi:
        with open(args.omit_AA_per_residue_multi) as fh:
            omit_AA_per_residue_multi = json.load(
                fh
            )  # {"pdb_path" : {"A12": "PQR", "A13": "QS"}}
    else:
        if args.omit_AA_per_residue:
            omit_AA_per_residue = args.omit_AA_per_residue  # {"A12": "PG"}
            omit_AA_per_residue_multi = {}
            for pdb in pdb_paths:
                omit_AA_per_residue_multi[pdb] = omit_AA_per_residue
    omit_AA_list = args.omit_AA
    omit_AA = torch.tensor(
        np.array([AA in omit_AA_list for AA in alphabet]).astype(np.float32),
        device=device,
    )

    if args.parse_these_chains_only:
        parse_these_chains_only_list = args.parse_these_chains_only
    else:
        parse_these_chains_only_list = []

    # loop over PDB paths
    for pdb in pdb_paths:
        if args.verbose:
            logger.debug("Designing protein from this path: %s", pdb)
        fixed_residues = fixed_residues_multi[pdb]
        redesigned_residues = redesigned_residues_multi[pdb]
        parse_all_atoms_flag = args.ligand_mpnn_use_side_chain_context or (
            args.pack_side_chains and not args.repack_everything
        )
        protein_dict, backbone, other_atoms, icodes, _ = parse_PDB(
            pdb,
            device=device,
            chains=parse_these_chains_only_list,
            parse_all_atoms=parse_all_atoms_flag,
            parse_atoms_with_zero_occupancy=args.parse_atoms_with_zero_occupancy,
        )
        # make chain_letter + residue_idx + insertion_code mapping to integers
        R_idx_list = list(protein_dict["R_idx"].cpu().numpy())  # residue indices
        chain_letters_list = list(protein_dict["chain_letters"])  # chain letters
        encoded_residues = []
        for i, R_idx_item in enumerate(R_idx_list):
            tmp = str(chain_letters_list[i]) + str(R_idx_item) + icodes[i]
            encoded_residues.append(tmp)
        encoded_residue_dict = dict(
            zip(encoded_residues, range(len(encoded_residues)), strict=False)
        )
        encoded_residue_dict_rev = dict(
            zip(list(range(len(encoded_residues))), encoded_residues, strict=False)
        )
        bias_AA_per_residue = torch.zeros(
            [len(encoded_residues), 21], device=device, dtype=torch.float32
        )
        if args.bias_AA_per_residue_multi or args.bias_AA_per_residue:
            bias_dict = bias_AA_per_residue_multi[pdb]
            for residue_name, v1 in bias_dict.items():
                if residue_name in encoded_residues:
                    i1 = encoded_residue_dict[residue_name]
                    for amino_acid, v2 in v1.items():
                        if amino_acid in alphabet:
                            j1 = restype_str_to_int[amino_acid]
                            bias_AA_per_residue[i1, j1] = v2

        omit_AA_per_residue = torch.zeros(
            [len(encoded_residues), 21], device=device, dtype=torch.float32
        )
        if args.omit_AA_per_residue_multi or args.omit_AA_per_residue:
            omit_dict = omit_AA_per_residue_multi[pdb]
            for residue_name, v1 in omit_dict.items():
                if residue_name in encoded_residues:
                    i1 = encoded_residue_dict[residue_name]
                    for amino_acid in v1:
                        if amino_acid in alphabet:
                            j1 = restype_str_to_int[amino_acid]
                            omit_AA_per_residue[i1, j1] = 1.0

        fixed_positions = torch.tensor(
            [int(item not in fixed_residues) for item in encoded_residues],
            device=device,
        )
        redesigned_positions = torch.tensor(
            [int(item not in redesigned_residues) for item in encoded_residues],
            device=device,
        )

        # specify which residues are buried for checkpoint_per_residue_label_membrane_mpnn model
        if args.transmembrane_buried:
            buried_residues = args.transmembrane_buried
            buried_positions = torch.tensor(
                [int(item in buried_residues) for item in encoded_residues],
                device=device,
            )
        else:
            buried_positions = torch.zeros_like(fixed_positions)

        if args.transmembrane_interface:
            interface_residues = args.transmembrane_interface
            interface_positions = torch.tensor(
                [int(item in interface_residues) for item in encoded_residues],
                device=device,
            )
        else:
            interface_positions = torch.zeros_like(fixed_positions)
        protein_dict["membrane_per_residue_labels"] = 2 * buried_positions * (
            1 - interface_positions
        ) + 1 * interface_positions * (1 - buried_positions)

        if args.model_type == "global_label_membrane_mpnn":
            protein_dict["membrane_per_residue_labels"] = (
                args.global_transmembrane_label + 0 * fixed_positions
            )
        if len(args.chains_to_design) != 0:
            chains_to_design_list = args.chains_to_design
        else:
            chains_to_design_list = protein_dict["chain_letters"]

        chain_mask = torch.tensor(
            np.array(
                [
                    item in chains_to_design_list
                    for item in protein_dict["chain_letters"]
                ],
                dtype=np.int32,
            ),
            device=device,
        )

        # create chain_mask to notify which residues are fixed (0) and which need to be designed (1)
        if redesigned_residues:
            protein_dict["chain_mask"] = chain_mask * (1 - redesigned_positions)
        elif fixed_residues:
            protein_dict["chain_mask"] = chain_mask * fixed_positions
        else:
            protein_dict["chain_mask"] = chain_mask

        if args.verbose:
            PDB_residues_to_be_redesigned = [
                encoded_residue_dict_rev[item]
                for item in range(protein_dict["chain_mask"].shape[0])
                if protein_dict["chain_mask"][item] == 1
            ]
            PDB_residues_to_be_fixed = [
                encoded_residue_dict_rev[item]
                for item in range(protein_dict["chain_mask"].shape[0])
                if protein_dict["chain_mask"][item] == 0
            ]
            logger.debug(
                "These residues will be redesigned: %s", PDB_residues_to_be_redesigned
            )
            logger.debug("These residues will be fixed: %s", PDB_residues_to_be_fixed)

        # specify which residues are linked
        if args.symmetry_residues:
            symmetry_residues_list_of_lists = args.symmetry_residues
            remapped_symmetry_residues = []
            for t_list in symmetry_residues_list_of_lists:
                tmp_list = []
                for t in t_list:
                    tmp_list.append(encoded_residue_dict[t])
                remapped_symmetry_residues.append(tmp_list)
        else:
            remapped_symmetry_residues = [[]]

        # specify linking weights
        if args.symmetry_weights:
            symmetry_weights = args.symmetry_weights
        else:
            symmetry_weights = [[]]

        if args.homo_oligomer:
            if args.verbose:
                logger.debug("Designing HOMO-OLIGOMER")
            chain_letters_set = list(set(chain_letters_list))
            reference_chain = chain_letters_set[0]
            lc = len(reference_chain)
            residue_indices = [
                item[lc:] for item in encoded_residues if item[:lc] == reference_chain
            ]
            remapped_symmetry_residues = []
            symmetry_weights = []
            for res in residue_indices:
                tmp_list = []
                tmp_w_list = []
                for chain in chain_letters_set:
                    name = chain + res
                    tmp_list.append(encoded_residue_dict[name])
                    tmp_w_list.append(1 / len(chain_letters_set))
                remapped_symmetry_residues.append(tmp_list)
                symmetry_weights.append(tmp_w_list)

        # set other atom bfactors to 0.0
        if other_atoms:
            other_bfactors = other_atoms.getBetas()
            other_atoms.setBetas(other_bfactors * 0.0)

        # adjust input PDB name by dropping .pdb if it does exist
        name = pdb[pdb.rfind("/") + 1 :]
        if name[-4:] == ".pdb":
            name = name[:-4]

        with torch.no_grad():
            # run featurize to remap R_idx and add batch dimension
            if args.verbose:
                if "Y" in list(protein_dict):
                    atom_coords = protein_dict["Y"].cpu().numpy()
                    atom_types: list[Any] = list(protein_dict["Y_t"].cpu().numpy())
                    atom_mask = list(protein_dict["Y_m"].cpu().numpy())
                    number_of_atoms_parsed = np.sum(atom_mask)
                else:
                    logger.debug("No ligand atoms parsed")
                    number_of_atoms_parsed = 0
                    atom_types = []
                    atom_coords = []
                if number_of_atoms_parsed == 0:
                    logger.debug("No ligand atoms parsed")
                elif args.model_type == "ligand_mpnn":
                    logger.debug(
                        "The number of ligand atoms parsed is equal to: %s",
                        number_of_atoms_parsed,
                    )
                    for i, atom_type in enumerate(atom_types):
                        logger.debug(
                            f"Type: {element_dict_rev[atom_type]}, Coords {atom_coords[i]}, Mask {atom_mask[i]}"
                        )
            feature_dict = featurize(
                protein_dict,
                cutoff_for_score=args.ligand_mpnn_cutoff_for_score,
                use_atom_context=args.ligand_mpnn_use_atom_context,
                number_of_ligand_atoms=atom_context_num,
                model_type=args.model_type,
            )
            feature_dict["batch_size"] = args.batch_size
            B, L, _, _ = feature_dict["X"].shape  # batch size should be 1 for now.
            # add additional keys to the feature dictionary
            feature_dict["temperature"] = args.temperature
            feature_dict["bias"] = (
                (-1e8 * omit_AA[None, None, :] + bias_AA).repeat([1, L, 1])
                + bias_AA_per_residue[None]
                - 1e8 * omit_AA_per_residue[None]
            )
            feature_dict["symmetry_residues"] = remapped_symmetry_residues
            feature_dict["symmetry_weights"] = symmetry_weights

            sampling_probs_list = []
            log_probs_list = []
            decoding_order_list = []
            S_list = []
            loss_list = []
            loss_per_residue_list = []
            loss_XY_list = []
            for _ in range(args.number_of_batches):
                feature_dict["randn"] = torch.randn(
                    [feature_dict["batch_size"], feature_dict["mask"].shape[1]],
                    device=device,
                )
                output_dict = model.sample(feature_dict)

                # compute confidence scores
                loss, loss_per_residue = get_score(
                    output_dict["S"],
                    output_dict["log_probs"],
                    feature_dict["mask"] * feature_dict["chain_mask"],
                )
                if args.model_type == "ligand_mpnn":
                    combined_mask = (
                        feature_dict["mask"]
                        * feature_dict["mask_XY"]
                        * feature_dict["chain_mask"]
                    )
                else:
                    combined_mask = feature_dict["mask"] * feature_dict["chain_mask"]
                loss_XY, _ = get_score(
                    output_dict["S"], output_dict["log_probs"], combined_mask
                )
                # -----
                S_list.append(output_dict["S"])
                log_probs_list.append(output_dict["log_probs"])
                sampling_probs_list.append(output_dict["sampling_probs"])
                decoding_order_list.append(output_dict["decoding_order"])
                loss_list.append(loss)
                loss_per_residue_list.append(loss_per_residue)
                loss_XY_list.append(loss_XY)
            S_stack = torch.cat(S_list, 0)
            log_probs_stack = torch.cat(log_probs_list, 0)
            sampling_probs_stack = torch.cat(sampling_probs_list, 0)
            decoding_order_stack = torch.cat(decoding_order_list, 0)
            loss_stack = torch.cat(loss_list, 0)
            loss_per_residue_stack = torch.cat(loss_per_residue_list, 0)
            loss_XY_stack = torch.cat(loss_XY_list, 0)
            rec_mask = feature_dict["mask"][:1] * feature_dict["chain_mask"][:1]
            rec_stack = get_seq_rec(feature_dict["S"][:1], S_stack, rec_mask)

            native_seq = "".join(
                [restype_int_to_str[AA] for AA in feature_dict["S"][0].cpu().numpy()]
            )
            seq_np = np.array(list(native_seq))
            seq_out_parts: list[Any] = []
            for mask in protein_dict["mask_c"]:
                seq_out_parts += list(seq_np[mask.cpu().numpy()])
                seq_out_parts += [args.fasta_seq_separation]
            seq_out_str = "".join(seq_out_parts)[:-1]

            output_fasta = base_folder + "/seqs/" + name + args.file_ending + ".fa"
            output_backbones = base_folder + "/backbones/"
            output_packed = base_folder + "/packed/"
            # output_stats_path = base_folder + "stats/" + name + args.file_ending + ".pt"

            out_dict = {}
            out_dict["generated_sequences"] = S_stack.cpu()
            out_dict["sampling_probs"] = sampling_probs_stack.cpu()
            out_dict["log_probs"] = log_probs_stack.cpu()
            out_dict["decoding_order"] = decoding_order_stack.cpu()
            out_dict["native_sequence"] = feature_dict["S"][0].cpu()
            out_dict["mask"] = feature_dict["mask"][0].cpu()
            out_dict["chain_mask"] = feature_dict["chain_mask"][0].cpu()
            out_dict["temperature"] = args.temperature

            results_dict_list = []

            if args.pack_side_chains:
                if args.verbose:
                    logger.debug("Packing side chains...")
                feature_dict_ = featurize(
                    protein_dict,
                    cutoff_for_score=8.0,
                    use_atom_context=args.pack_with_ligand_context,
                    number_of_ligand_atoms=16,
                    model_type="ligand_mpnn",
                )
                sc_feature_dict = copy.deepcopy(feature_dict_)
                B = args.batch_size
                for k, v in sc_feature_dict.items():
                    if k != "S":
                        try:
                            num_dim = len(v.shape)
                            if num_dim == 2:
                                sc_feature_dict[k] = v.repeat(B, 1)
                            elif num_dim == 3:
                                sc_feature_dict[k] = v.repeat(B, 1, 1)
                            elif num_dim == 4:
                                sc_feature_dict[k] = v.repeat(B, 1, 1, 1)
                            elif num_dim == 5:
                                sc_feature_dict[k] = v.repeat(B, 1, 1, 1, 1)
                        except:  # noqa: E722
                            pass
                X_stack_list = []
                X_m_stack_list = []
                b_factor_stack_list = []
                for _ in range(args.number_of_packs_per_design):
                    X_list = []
                    X_m_list = []
                    b_factor_list = []
                    for c in range(args.number_of_batches):
                        sc_feature_dict["S"] = S_list[c]
                        sc_dict = pack_side_chains(
                            sc_feature_dict,
                            model_sc,
                            args.sc_num_denoising_steps,
                            args.sc_num_samples,
                            args.repack_everything,
                        )
                        X_list.append(sc_dict["X"])
                        X_m_list.append(sc_dict["X_m"])
                        b_factor_list.append(sc_dict["b_factors"])

                    X_stack = torch.cat(X_list, 0)
                    X_m_stack = torch.cat(X_m_list, 0)
                    b_factor_stack = torch.cat(b_factor_list, 0)

                    X_stack_list.append(X_stack)
                    X_m_stack_list.append(X_m_stack)
                    b_factor_stack_list.append(b_factor_stack)

            with open(output_fasta, "w") as f:  # noqa: F841
                # f.write(
                #     ">{}, T={}, seed={}, num_res={}, num_ligand_res={}, use_ligand_context={}, ligand_cutoff_distance={}, batch_size={}, number_of_batches={}, model_path={}\n{}\n".format(
                #         name,
                #         args.temperature,
                #         seed,
                #         torch.sum(rec_mask).cpu().numpy(),
                #         torch.sum(combined_mask[:1]).cpu().numpy(),
                #         bool(args.ligand_mpnn_use_atom_context),
                #         float(args.ligand_mpnn_cutoff_for_score),
                #         args.batch_size,
                #         args.number_of_batches,
                #         checkpoint_path,
                #         seq_out_str,
                #     )
                # )

                for ix in range(S_stack.shape[0]):
                    results_dict: dict[str, Any] = {}

                    ix_suffix = ix
                    if not args.zero_indexed:
                        ix_suffix += 1
                    seq_rec_print = np.format_float_positional(
                        rec_stack[ix].cpu().numpy(), unique=False, precision=4
                    )
                    loss_np = np.format_float_positional(
                        np.exp(-loss_stack[ix].cpu().numpy()), unique=False, precision=4
                    )
                    loss_XY_np = np.format_float_positional(
                        np.exp(-loss_XY_stack[ix].cpu().numpy()),
                        unique=False,
                        precision=4,
                    )
                    seq = "".join(
                        [restype_int_to_str[AA] for AA in S_stack[ix].cpu().numpy()]
                    )

                    # write new sequences into PDB with backbone coordinates
                    seq_prody = np.array([restype_1to3[AA] for AA in list(seq)])[
                        None,
                    ].repeat(4, 1)
                    bfactor_prody = (
                        loss_per_residue_stack[ix].cpu().numpy()[None, :].repeat(4, 1)
                    )
                    backbone.setResnames(seq_prody)
                    backbone.setBetas(
                        np.exp(-bfactor_prody)
                        * (bfactor_prody > 0.01).astype(np.float32)
                    )
                    if other_atoms:
                        writePDB(
                            output_backbones + name + "_" + str(ix_suffix) + ".pdb",
                            backbone + other_atoms,
                        )
                    else:
                        writePDB(
                            output_backbones + name + "_" + str(ix_suffix) + ".pdb",
                            backbone,
                        )

                    with open(
                        output_backbones + name + "_" + str(ix_suffix) + ".pdb"
                    ) as pdb_file:
                        pdb_str = pdb_file.read()

                    results_dict["pdb"] = pdb_str

                    # write full PDB files
                    if args.pack_side_chains:
                        results_dict["pdb_packed"] = {}
                        for c_pack in range(args.number_of_packs_per_design):
                            X_stack = X_stack_list[c_pack]
                            X_m_stack = X_m_stack_list[c_pack]
                            b_factor_stack = b_factor_stack_list[c_pack]
                            write_full_PDB(
                                output_packed
                                + name
                                + "_packed"
                                + "_"
                                + str(ix_suffix)
                                + "_"
                                + str(c_pack + 1)
                                + ".pdb",
                                X_stack[ix].cpu().numpy(),
                                X_m_stack[ix].cpu().numpy(),
                                b_factor_stack[ix].cpu().numpy(),
                                feature_dict["R_idx_original"][0].cpu().numpy(),
                                protein_dict["chain_letters"],
                                S_stack[ix].cpu().numpy(),
                                other_atoms=other_atoms,
                                icodes=icodes,
                                force_hetatm=args.force_hetatm,
                            )

                            with open(
                                output_packed
                                + name
                                + "_packed"
                                + "_"
                                + str(ix_suffix)
                                + "_"
                                + str(c_pack + 1)
                                + ".pdb",
                            ) as pdb_file:
                                pdb_str_packed = pdb_file.read()

                            results_dict["pdb_packed"][
                                f"packed_{c_pack + 1}"
                            ] = pdb_str_packed

                    # -----

                    # write fasta lines
                    seq_np = np.array(list(seq))
                    seq_out_parts = []
                    for mask in protein_dict["mask_c"]:
                        seq_out_parts += list(seq_np[mask.cpu().numpy()])
                        seq_out_parts += [args.fasta_seq_separation]
                    seq_out_str = "".join(seq_out_parts)[:-1]
                    results_dict["sequence"] = seq_out_str
                    results_dict["overall_confidence"] = loss_np
                    results_dict["ligand_confidence"] = loss_XY_np
                    results_dict["seq_rec"] = seq_rec_print
                    results_dict["log_probs"] = out_dict["log_probs"][ix].tolist()
                    results_dict["sampling_probs"] = out_dict["sampling_probs"][
                        ix
                    ].tolist()
                    results_dict_list.append(results_dict)
                    # if ix == S_stack.shape[0] - 1:
                    #     # final 2 lines
                    #     f.write(
                    #         ">{}, id={}, T={}, seed={}, overall_confidence={}, ligand_confidence={}, seq_rec={}\n{}".format(
                    #             name,
                    #             ix_suffix,
                    #             args.temperature,
                    #             seed,
                    #             loss_np,
                    #             loss_XY_np,
                    #             seq_rec_print,
                    #             seq_out_str,
                    #         )
                    #     )
                    # else:
                    #     f.write(
                    #         ">{}, id={}, T={}, seed={}, overall_confidence={}, ligand_confidence={}, seq_rec={}\n{}\n".format(
                    #             name,
                    #             ix_suffix,
                    #             args.temperature,
                    #             seed,
                    #             loss_np,
                    #             loss_XY_np,
                    #             seq_rec_print,
                    #             seq_out_str,
                    #         )
                    #     )
    return results_dict_list
