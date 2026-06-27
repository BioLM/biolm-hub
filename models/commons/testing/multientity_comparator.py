"""
Multi-entity mmCIF structure comparator for handling complex molecular structures.

This module provides specialized comparison for multi-entity structures containing:
- Proteins
- DNA/RNA
- Small molecule ligands
- Ions

Algorithm:
1. Entity Classification: Parse structures and classify each chain by molecule type
   (protein/DNA/RNA/ligand/ion) based on residue names
2. Chain Matching: Match chains between structures using sequence similarity (90% for
   polymers) or atom count similarity (for ligands)
3. Per-Entity RMSD: Calculate RMSD separately for each matched chain pair, handling
   atom mismatches by residue/atom name matching
4. Weighted Scoring: Compute atom-count-weighted average RMSD and check each entity
   type against its specific threshold

Design Rationale:
- Chain Matching (90% similarity): Handles chain reordering while preventing mis-matches
- Per-Entity RMSD: Different molecules have different flexibility (3Å acceptable for
  proteins, catastrophic for ligands)
- Atom-Count Weighting: Larger molecules contribute more to overall quality score
- Entity-Specific Thresholds: Proteins (5.0Å - acceptable fold in complexes),
  DNA/RNA (9.0Å - allows bending/unwinding/ribosomal movements),
  Ligands (2.0Å - binding site tolerance), Ions (1.0Å - coordination flexibility)

When to use this comparator:
- Structure contains multiple molecule types (protein + RNA/DNA/ligand)
- Multi-chain complexes where chains may be reordered
- Need per-entity type RMSD thresholds
- Standard comparator gives unrealistic high RMSD (>10Å)

Models currently using: boltz1, boltz2
Potential future users: chai1 (multi-chain complexes), af2_nim (AlphaFold predictions),
                       esmfold (protein structures), immunebuilder (antibody complexes)
"""

import warnings
from collections import defaultdict
from io import StringIO
from typing import Any, Optional

from Bio import pairwise2
from Bio.PDB import MMCIFParser, Superimposer
from Bio.PDB.Chain import Chain
from Bio.PDB.Structure import Structure
from Bio.SeqUtils import seq1

# Suppress Bio warnings
warnings.filterwarnings("ignore", module="Bio.PDB")


class EntityType:
    """Entity type classification"""

    PROTEIN = "protein"
    DNA = "dna"
    RNA = "rna"
    LIGAND = "ligand"
    ION = "ion"
    UNKNOWN = "unknown"


class MultiEntitymmCIFComparator:
    """Comparator for multi-entity mmCIF structures"""

    def __init__(
        self,
        protein_rmsd_threshold: float = 5.0,
        dna_rmsd_threshold: float = 9.0,
        rna_rmsd_threshold: float = 9.0,
        ligand_rmsd_threshold: float = 2.0,
        ion_rmsd_threshold: float = 1.0,
        min_sequence_similarity: float = 0.9,
        verbose: bool = True,
    ):
        """
        Initialize the multi-entity comparator with per-entity type thresholds.

        Args:
            protein_rmsd_threshold: Max RMSD for proteins (default: 5.0Å)
            dna_rmsd_threshold: Max RMSD for DNA (default: 9.0Å - allows bending/unwinding)
            rna_rmsd_threshold: Max RMSD for RNA (default: 9.0Å - ribosomal flexibility)
            ligand_rmsd_threshold: Max RMSD for small molecules (default: 2.0Å)
            ion_rmsd_threshold: Max RMSD for ions (default: 1.0Å)
            min_sequence_similarity: Minimum sequence similarity for chain matching (default: 0.9)
            verbose: Whether to print detailed comparison information
        """
        self.thresholds = {
            EntityType.PROTEIN: protein_rmsd_threshold,
            EntityType.DNA: dna_rmsd_threshold,
            EntityType.RNA: rna_rmsd_threshold,
            EntityType.LIGAND: ligand_rmsd_threshold,
            EntityType.ION: ion_rmsd_threshold,
            EntityType.UNKNOWN: 5.0,  # Fallback for unrecognized entities
        }
        self.min_sequence_similarity = min_sequence_similarity
        self.verbose = verbose
        self.parser = MMCIFParser(QUIET=True)

    def compare(  # noqa: C901  # Complex bioinformatics algorithm - complexity justified
        self, expected_cif: str, predicted_cif: str
    ) -> tuple[float, dict[str, Any]]:
        """
        Compare two mmCIF structures with multi-modal awareness.

        Returns:
            Tuple of (overall_rmsd, details_dict)
        """
        # Parse structures
        expected = self._parse_structure(expected_cif, "expected")
        predicted = self._parse_structure(predicted_cif, "predicted")

        if not expected or not predicted:
            return float("inf"), {"error": "Failed to parse structures"}

        # Classify entities by type
        expected_entities = self._classify_entities(expected)
        predicted_entities = self._classify_entities(predicted)

        if self.verbose:
            print(f"Expected entities: {self._summarize_entities(expected_entities)}")
            print(f"Predicted entities: {self._summarize_entities(predicted_entities)}")

        # Match chains between structures
        chain_matches = self._match_chains(expected_entities, predicted_entities)

        if not chain_matches:
            if self.verbose:
                print(
                    "Warning: No matching chains found, falling back to naive alignment"
                )
            # Fall back to naive all-atom RMSD
            return self._calculate_naive_rmsd(expected, predicted), {"method": "naive"}

        # Calculate per-entity RMSD
        entity_results = {}
        total_weighted_rmsd = 0.0
        total_weight = 0.0

        for entity_type, matches in chain_matches.items():
            if not matches:
                continue

            type_rmsd = []
            type_atoms = 0

            for exp_chain_id, pred_chain_id, similarity in matches:
                exp_chain = self._get_chain(expected, exp_chain_id)
                pred_chain = self._get_chain(predicted, pred_chain_id)

                if exp_chain and pred_chain:
                    rmsd, n_atoms = self._calculate_chain_rmsd(exp_chain, pred_chain)
                    if rmsd is not None:
                        type_rmsd.append(rmsd)
                        type_atoms += n_atoms

                        if self.verbose:
                            print(
                                f"  {entity_type} chain {exp_chain_id} -> {pred_chain_id}: "
                                f"RMSD={rmsd:.2f}Å, atoms={n_atoms}, similarity={similarity:.2f}"
                            )

            if type_rmsd:
                avg_rmsd = sum(type_rmsd) / len(type_rmsd)
                entity_results[entity_type] = {
                    "rmsd": avg_rmsd,
                    "n_chains": len(type_rmsd),
                    "n_atoms": type_atoms,
                    "threshold": self.thresholds[entity_type],
                    "pass": avg_rmsd <= self.thresholds[entity_type],
                }

                # Weight by number of atoms for overall score
                weight = type_atoms
                total_weighted_rmsd += avg_rmsd * weight
                total_weight += weight

        # Calculate overall RMSD
        if total_weight > 0:
            overall_rmsd = total_weighted_rmsd / total_weight
        else:
            overall_rmsd = float("inf")

        # Check if all entity types pass their thresholds
        all_pass = all(r.get("pass", False) for r in entity_results.values())

        result = {
            "overall_rmsd": overall_rmsd,
            "entity_results": entity_results,
            "all_pass": all_pass,
            "method": "multientity",
        }

        if self.verbose:
            print(f"\nOverall weighted RMSD: {overall_rmsd:.2f}Å")
            print(f"All entity types pass: {all_pass}")

        return overall_rmsd, result

    def _parse_structure(self, cif_str: str, name: str) -> Optional[Structure]:
        """Parse mmCIF string to BioPython Structure"""
        try:
            io = StringIO(cif_str)
            return self.parser.get_structure(name, io)
        except Exception as e:
            if self.verbose:
                print(f"Error parsing structure '{name}': {e}")
            return None

    def _classify_entities(self, structure: Structure) -> dict[str, list[Chain]]:
        """Classify chains by entity type"""
        entities = defaultdict(list)

        for model in structure:
            for chain in model:
                entity_type = self._determine_entity_type(chain)
                entities[entity_type].append(chain)

        return dict(entities)

    def _determine_entity_type(self, chain: Chain) -> str:
        """Determine the type of entity from a chain"""
        residues = list(chain.get_residues())
        if not residues:
            return EntityType.UNKNOWN

        # Check for nucleotides
        nucleotide_names = {"A", "T", "G", "C", "U", "DA", "DT", "DG", "DC", "DU"}
        rna_names = {"A", "G", "C", "U"}
        dna_names = {"DA", "DT", "DG", "DC"}

        residue_names = {r.resname.strip() for r in residues}

        # Check for RNA/DNA
        if residue_names & rna_names:
            return EntityType.RNA
        if residue_names & dna_names:
            return EntityType.DNA
        if residue_names & nucleotide_names:
            # Generic nucleotide, guess based on presence of U vs T
            if "U" in residue_names:
                return EntityType.RNA
            else:
                return EntityType.DNA

        # Check for protein
        amino_acids = {
            "ALA",
            "ARG",
            "ASN",
            "ASP",
            "CYS",
            "GLN",
            "GLU",
            "GLY",
            "HIS",
            "ILE",
            "LEU",
            "LYS",
            "MET",
            "PHE",
            "PRO",
            "SER",
            "THR",
            "TRP",
            "TYR",
            "VAL",
        }

        if any(r.resname.strip() in amino_acids for r in residues):
            return EntityType.PROTEIN

        # Check for ions (single atom residues)
        if len(residues) == 1 and len(list(residues[0].get_atoms())) <= 2:
            return EntityType.ION

        # Small molecules/ligands (HETATM records, non-standard residues)
        if all(r.id[0].strip() != " " for r in residues):  # HETATM records
            return EntityType.LIGAND

        # If mostly non-standard residues, likely a ligand
        if len(residues) < 10:  # Small chain
            return EntityType.LIGAND

        return EntityType.UNKNOWN

    def _match_chains(
        self,
        expected_entities: dict[str, list[Chain]],
        predicted_entities: dict[str, list[Chain]],
    ) -> dict[str, list[tuple[str, str, float]]]:
        """Match chains between structures by entity type and sequence similarity"""
        matches = defaultdict(list)

        for entity_type in expected_entities:
            if entity_type not in predicted_entities:
                continue

            exp_chains = expected_entities[entity_type]
            pred_chains = predicted_entities[entity_type]

            # For each expected chain, find best matching predicted chain
            used_pred_chains = set()

            for exp_chain in exp_chains:
                best_match = None
                best_similarity = 0.0

                for pred_chain in pred_chains:
                    if pred_chain.id in used_pred_chains:
                        continue

                    similarity = self._calculate_sequence_similarity(
                        exp_chain, pred_chain
                    )

                    if (
                        similarity > best_similarity
                        and similarity >= self.min_sequence_similarity
                    ):
                        best_match = pred_chain.id
                        best_similarity = similarity

                if best_match:
                    matches[entity_type].append(
                        (exp_chain.id, best_match, best_similarity)
                    )
                    used_pred_chains.add(best_match)

        return dict(matches)

    def _calculate_sequence_similarity(self, chain1: Chain, chain2: Chain) -> float:
        """Calculate sequence similarity between two chains"""
        try:
            seq1_str = self._extract_sequence(chain1)
            seq2_str = self._extract_sequence(chain2)

            if not seq1_str or not seq2_str:
                # For non-sequence entities (ligands), compare by atom count
                n1 = len(list(chain1.get_atoms()))
                n2 = len(list(chain2.get_atoms()))
                # Simple similarity based on atom count
                return 1.0 - abs(n1 - n2) / max(n1, n2) if max(n1, n2) > 0 else 0.0

            # For sequences, use alignment score
            alignments = pairwise2.align.globalxx(seq1_str, seq2_str)
            if alignments:
                score = alignments[0].score
                max_len = max(len(seq1_str), len(seq2_str))
                return score / max_len if max_len > 0 else 0.0

            return 0.0

        except Exception:
            # Fall back to atom count similarity
            n1 = len(list(chain1.get_atoms()))
            n2 = len(list(chain2.get_atoms()))
            return 1.0 - abs(n1 - n2) / max(n1, n2) if max(n1, n2) > 0 else 0.0

    def _extract_sequence(self, chain: Chain) -> str:
        """Extract sequence from a chain"""
        sequence = []
        for residue in chain:
            if residue.id[0] == " ":  # Standard residue
                try:
                    # Convert 3-letter code to 1-letter
                    one_letter = seq1(residue.resname)
                    sequence.append(one_letter)
                except Exception:
                    # For non-standard residues, use X
                    sequence.append("X")
        return "".join(sequence)

    def _get_chain(self, structure: Structure, chain_id: str) -> Optional[Chain]:
        """Get a chain from structure by ID"""
        for model in structure:
            if chain_id in model:
                return model[chain_id]
        return None

    def _calculate_chain_rmsd(
        self, chain1: Chain, chain2: Chain
    ) -> tuple[Optional[float], int]:
        """Calculate RMSD between two chains"""
        atoms1 = list(chain1.get_atoms())
        atoms2 = list(chain2.get_atoms())

        if len(atoms1) != len(atoms2):
            # Try to match by residue and atom name
            atoms1, atoms2 = self._match_atoms(chain1, chain2)

        if not atoms1 or not atoms2 or len(atoms1) != len(atoms2):
            return None, 0

        try:
            super_imposer = Superimposer()
            super_imposer.set_atoms(atoms1, atoms2)
            rmsd = super_imposer.rms
            return rmsd, len(atoms1)
        except Exception as e:
            if self.verbose:
                print(f"Error calculating RMSD: {e}")
            return None, 0

    def _match_atoms(self, chain1: Chain, chain2: Chain) -> tuple[list, list]:
        """Match atoms between chains by residue and atom name"""
        atoms1 = []
        atoms2 = []

        res1_dict = {res.id: res for res in chain1}
        res2_dict = {res.id: res for res in chain2}

        for res_id in res1_dict:
            if res_id not in res2_dict:
                continue

            res1 = res1_dict[res_id]
            res2 = res2_dict[res_id]

            atom1_dict = {atom.name: atom for atom in res1}
            atom2_dict = {atom.name: atom for atom in res2}

            for atom_name in atom1_dict:
                if atom_name in atom2_dict:
                    atoms1.append(atom1_dict[atom_name])
                    atoms2.append(atom2_dict[atom_name])

        return atoms1, atoms2

    def _calculate_naive_rmsd(
        self, structure1: Structure, structure2: Structure
    ) -> float:
        """Calculate naive all-atom RMSD as fallback"""
        atoms1 = list(structure1.get_atoms())
        atoms2 = list(structure2.get_atoms())

        if len(atoms1) != len(atoms2):
            return float("inf")

        try:
            super_imposer = Superimposer()
            super_imposer.set_atoms(atoms1, atoms2)
            return super_imposer.rms
        except Exception:
            return float("inf")

    def _summarize_entities(self, entities: dict[str, list[Chain]]) -> str:
        """Create a summary string of entities"""
        summary = []
        for entity_type, chains in entities.items():
            chain_ids = [c.id for c in chains]
            summary.append(f"{entity_type}={chain_ids}")
        return ", ".join(summary)
