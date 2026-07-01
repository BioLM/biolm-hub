from io import StringIO
from math import sqrt
from typing import Any, Optional

from Bio.PDB.MMCIFParser import MMCIFParser
from Bio.PDB.PDBParser import PDBParser


class DictComparator:
    def __init__(
        self,
        rel_tol: float = 1e-5,
        abs_tol: Optional[float] = None,  # absolute tolerance for near-zero values
        ignore_paths: Optional[
            set[str]
        ] = None,  # skip these dot-separated paths (e.g. "results.0.cif")
        cosine_distance_threshold: Optional[float] = None,  # range between (0, 1)
        pdb_rmsd_threshold: Optional[float] = None,
        pdb_seq_match: bool = False,
        is_generated_seq: bool = False,
        msa_content_len_threshold: Optional[float] = None,
        multientity_mmcif_comparison: bool = False,  # Enable multi-entity comparator
    ):
        self.rel_tol = rel_tol
        self.abs_tol = abs_tol
        self.ignore_paths = ignore_paths or set()
        self.cosine_distance_threshold = cosine_distance_threshold
        self.pdb_rmsd_threshold = pdb_rmsd_threshold
        self.pdb_seq_match = pdb_seq_match  # if true, compare pdb sequences (not RMSD)
        self.is_generated_seq = is_generated_seq
        self.msa_content_len_threshold = msa_content_len_threshold
        self.multientity_mmcif_comparison = multientity_mmcif_comparison
        self.max_diff: float = 0
        self.max_diff_path: list[Any] = []
        self.max_diff_values = (None, None)

        # Enforce the invariant: if pdb_seq_match is True, pdb_rmsd_threshold must be None.
        if pdb_seq_match and pdb_rmsd_threshold is not None:
            raise ValueError(
                "pdb_seq_match=True requires pdb_rmsd_threshold to be None"
            )

        # Internal constants
        self._inf_diff: float = 1e10
        self._red_start = "\033[91m"
        self._red_end = "\033[0m"

    def compare(self, dict1: dict[Any, Any], dict2: dict[Any, Any]) -> bool:
        self._compare_dicts(["root"], dict1, dict2)
        return self.max_diff <= self.rel_tol

    def _compare_dicts(
        self, path: list[Any], dict1: dict[Any, Any], dict2: dict[Any, Any]
    ) -> None:
        for key in sorted(dict1.keys() | dict2.keys()):
            # Check if this path should be skipped (e.g. "results.0.cif")
            full_path = ".".join(str(p) for p in path[1:] + [key])  # skip "root"
            if full_path in self.ignore_paths:
                continue
            if key in dict1 and key in dict2:
                self._compare_values(path + [key], dict1[key], dict2[key])
            else:
                # One of the dicts doesn't have this key
                print(
                    f">>> Key '{self._red_start}{key}{self._red_end}' at {self._diff_path_str(path)} is missing from one of the input dicts."
                )
                self._update_max_diff(
                    self._inf_diff, path + [key], (dict1.get(key), dict2.get(key))
                )

    def _compare_values(self, path: list[Any], value1: Any, value2: Any) -> None:
        # If dict, recursively check if the values are close
        if isinstance(value1, dict) and isinstance(value2, dict):
            self._compare_dicts(path, value1, value2)

        # If list, recursively check if the values are close
        elif isinstance(value1, list) and isinstance(value2, list):
            self._compare_lists(path, value1, value2)

        # If float or int, check if the values are close
        elif self._are_nums(value1, value2):
            self._compare_nums(path, value1, value2)

        # If PDB string, check if the RMSD is below the threshold
        elif self._are_pdbs(value1, value2):
            self._compare_pdbs(path, value1, value2)

        # If generated sequence, check if the lengths are the same
        elif self._are_generated_seqs(value1, value2):
            self._compare_generated_seq(path, value1, value2)

        # If FASTA strings, compare the sequence parts
        elif self.msa_content_len_threshold is not None:
            self._compare_msa_contents(path, value1, value2)

        # Otherwise, use default comparison logic (checks if values are equal)
        else:
            self._compare_default(path, value1, value2)

    def _are_nums(self, value1: Any, value2: Any) -> bool:
        return isinstance(value1, int | float) and isinstance(value2, int | float)

    def _are_pdbs(self, value1: Any, value2: Any) -> bool:
        return (
            (self.pdb_rmsd_threshold is not None or self.pdb_seq_match)
            and isinstance(value1, str)
            and isinstance(value2, str)
            and ("ATOM" in value1 or "_atom_site" in value1)
            and ("ATOM" in value2 or "_atom_site" in value2)
        )

    def _parse_structure(self, value: str, file_type: str = "pdb") -> Any:
        parser = (
            PDBParser(QUIET=True)  # type: ignore[no-untyped-call]  # biopython parser ctor is untyped
            if file_type == "pdb"
            else MMCIFParser(QUIET=True)  # type: ignore[no-untyped-call]  # biopython parser ctor is untyped
        )
        structure_id = "expected" if "expected" in value else "result"
        io = StringIO(value)
        try:
            return parser.get_structure(  # type: ignore[no-untyped-call]  # biopython get_structure is untyped
                structure_id, io
            )
        except Exception as e:
            print(f">>> Error parsing {file_type.upper()} file: {e}")
            return None

    def _are_generated_seqs(self, value1: Any, value2: Any) -> bool:
        return (
            self.is_generated_seq is True
            and isinstance(value1, str)
            and isinstance(value2, str)
        )

    def _compare_lists(
        self, path: list[Any], list1: list[Any], list2: list[Any]
    ) -> None:
        if len(list1) != len(list2):
            # Handle the case where lists are of different lengths
            print(f">>> Lists at {self._diff_path_str(path)} are different lengths.")
            self._update_max_diff(self._inf_diff, path, (list1, list2))
            return

        if len(list1) == 0:
            # Both lists are empty - they are equal
            self._update_max_diff(0.0, path, (list1, list2))
            return

        # Check for vector/matrix and handle with cosine distance if applicable
        if self.cosine_distance_threshold is not None:
            flat1 = self._flatten_list(list1)
            flat2 = self._flatten_list(list2)
            if flat1 is not None and flat2 is not None and len(flat1) == len(flat2):
                self._compare_vectors(path, flat1, flat2)
                return  # Skip element-wise recursion if handled as vector/matrix

        for i, (item1, item2) in enumerate(zip(list1, list2, strict=True)):
            self._compare_values(path + [i], item1, item2)

    def _compare_vectors(
        self, path: list[Any], flat1: list[float], flat2: list[float]
    ) -> None:
        # Only called from _compare_lists after confirming cosine_distance_threshold
        # is not None.
        assert self.cosine_distance_threshold is not None
        # Compute cosine similarity first (in pure Python), then derive distance
        dot = sum(a * b for a, b in zip(flat1, flat2, strict=True))
        norm1_sq = sum(a**2 for a in flat1)
        norm2_sq = sum(b**2 for b in flat2)
        norm1 = sqrt(norm1_sq)
        norm2 = sqrt(norm2_sq)

        if norm1 == 0 and norm2 == 0:
            cos_sim = 1.0  # Both zero: identical
        elif norm1 == 0 or norm2 == 0:
            cos_sim = 0.0  # One zero: orthogonal
        else:
            cos_sim = dot / (norm1 * norm2)

        cos_dist = (1 - cos_sim) / 2  # Reorient to distance (0=identical, 1=opposite)

        # print(f"Computed cosine distance at {self._diff_path_str(path)}: {cos_dist}")

        if cos_dist <= self.cosine_distance_threshold:
            # Within the cosine tolerance: record a pass by zeroing diff, exactly
            # like the PDB/MSA/generated-seq comparators. Recording cos_dist here
            # would re-gate it against the stricter final rel_tol check in
            # compare(), silently overriding cosine_distance_threshold.
            diff = 0.0
        else:
            print(
                f">>> Vectors/matrices at {self._diff_path_str(path)} differ beyond threshold: "
                f"cosine distance {cos_dist} > {self.cosine_distance_threshold}."
            )
            diff = self._inf_diff

        self._update_max_diff(diff, path, (flat1, flat2))

    def _compare_nums(self, path: list[Any], value1: Any, value2: Any) -> None:
        if value1 == value2:
            diff = 0.0
        elif self.abs_tol is not None and abs(value1 - value2) <= self.abs_tol:
            # Within absolute tolerance — treat as matching (handles near-zero sign flips)
            diff = 0.0
        elif value1 == 0 or value2 == 0:
            # If one is zero and the other isn't, use absolute difference
            diff = abs(value1 - value2)
        else:
            # Standard relative difference
            diff = abs(value1 - value2) / max(abs(value1), abs(value2))

        self._update_max_diff(diff, path, (value1, value2))

    def _compare_pdbs(self, path: list[Any], value1: str, value2: str) -> None:
        # Determine file type
        file_type = "cif" if "_atom_site" in value1 else "pdb"

        # Use multi-entity comparator for CIF files if enabled
        if self.multientity_mmcif_comparison and file_type == "cif":
            from models.commons.testing.multientity_comparator import (
                MultiEntitymmCIFComparator,
            )

            comparator = MultiEntitymmCIFComparator(
                protein_rmsd_threshold=self.pdb_rmsd_threshold or 3.0,
                verbose=False,  # Start quiet for performance
            )

            overall_rmsd, details = comparator.compare(value1, value2)

            # Check if comparison passed based on multi-entity criteria
            if details.get("all_pass", False):
                diff = 0.0
                print(
                    f"Multi-entity comparison PASSED at {self._diff_path_str(path)}: "
                    f"overall RMSD={overall_rmsd:.2f}Å"
                )
            else:
                # Failed - re-run with verbose to get detailed diagnostic output
                print(
                    f"\nMulti-entity comparison FAILED at {self._diff_path_str(path)}: "
                    f"overall RMSD={overall_rmsd:.2f}Å"
                )
                print("Re-running with verbose output for diagnostics:")
                comparator_verbose = MultiEntitymmCIFComparator(
                    protein_rmsd_threshold=self.pdb_rmsd_threshold or 3.0,
                    verbose=True,  # Enable verbose only for failures
                )
                comparator_verbose.compare(value1, value2)

                diff = overall_rmsd

            self._update_max_diff(diff, path, (value1, value2))
            return

        # If sequence matching mode is enabled, ignore any RMSD threshold.
        if self.pdb_seq_match:
            expected_structure = self._parse_structure(value1, file_type)
            result_structure = self._parse_structure(value2, file_type)
            if not expected_structure or not result_structure:
                print(">>> One or both structures could not be parsed.")
                diff = self._inf_diff
            else:
                expected_seq = self._extract_sequence(expected_structure)
                result_seq = self._extract_sequence(result_structure)
                # print(f"Extracted expected sequence: {expected_seq}")
                # print(f"Extracted result sequence: {result_seq}")
                diff = 0.0 if expected_seq == result_seq else self._inf_diff
            self._update_max_diff(diff, path, (value1, value2))
            return

        # Otherwise, use the standard RMSD-based comparison.
        expected_structure = self._parse_structure(value1, file_type)
        result_structure = self._parse_structure(value2, file_type)

        if not expected_structure or not result_structure:
            print(
                f">>> Error: Unable to parse one of the structures at {self._diff_path_str(path)}"
            )
            diff = self._inf_diff
            self._update_max_diff(diff, path, (value1, value2))
            return

        expected_atoms = list(expected_structure.get_atoms())
        result_atoms = list(result_structure.get_atoms())

        if not expected_atoms or not result_atoms:
            print(f">>> Missing atoms in structures at {self._diff_path_str(path)}")
            diff = self._inf_diff
            self._update_max_diff(diff, path, (value1, value2))
            return

        if len(expected_atoms) == len(result_atoms):
            from Bio.PDB.Superimposer import Superimposer

            # Only reached when not pdb_seq_match, so _are_pdbs already guarantees
            # pdb_rmsd_threshold is set.
            assert self.pdb_rmsd_threshold is not None
            super_imposer = Superimposer()  # type: ignore[no-untyped-call]  # biopython Superimposer ctor is untyped
            super_imposer.set_atoms(  # type: ignore[no-untyped-call]  # biopython set_atoms is untyped
                expected_atoms, result_atoms
            )
            rmsd = (
                super_imposer.rms if super_imposer.rms is not None else self._inf_diff
            )
            print(f"Computed RMSD at {self._diff_path_str(path)}: {rmsd}")
            diff = 0.0 if rmsd < self.pdb_rmsd_threshold else rmsd
        else:
            print(
                f">>> Structures have different numbers of atoms at {self._diff_path_str(path)}"
            )
            diff = self._inf_diff

        self._update_max_diff(diff, path, (value1, value2))

    def _compare_msa_contents(self, path: list[Any], value1: str, value2: str) -> None:
        """
        When dealing with MSAs, this method checks if the string lengths match within a 10%
        slack. If the relative difference in lengths is <= 10%, the diff is set to 0;
        otherwise, the diff is set to an infinite value.
        """
        # Only called from _compare_values after confirming msa_content_len_threshold
        # is not None.
        assert self.msa_content_len_threshold is not None
        len1 = len(value1)
        len2 = len(value2)
        # Calculate relative difference
        rel_diff = abs(len1 - len2) / max(len1, len2) if max(len1, len2) > 0 else 0
        if rel_diff <= self.msa_content_len_threshold:
            diff = 0.0
        else:
            print(
                f">>> MSA lengths at {self._diff_path_str(path)} differ beyond allowed slack: "
                f"{len1} vs {len2} (relative difference: {rel_diff:.2%} > {self.msa_content_len_threshold:.2%})."
            )
            diff = self._inf_diff
        self._update_max_diff(diff, path, (value1, value2))

    def _flatten_list(self, lst: list[Any]) -> Optional[list[float]]:  # noqa: C901
        # FIXME(noqa: C901): Refactor to reduce complexity below the linter's threshold.
        """
        Flatten vectors (1D), matrices (2D), or 3D tensors to 1D for cosine distance.
        Returns None if the input is not a valid numeric tensor (up to 3D).
        """

        def _is_numeric(x: Any) -> bool:
            return isinstance(x, int | float)

        def _flatten_recursive(obj: Any, depth: int = 0) -> Optional[list[float]]:
            if depth > 3:  # Limit to 3D tensors
                return None

            if not isinstance(obj, list) or not obj:
                return None

            # Check if this level is all numeric (1D vector)
            if all(_is_numeric(x) for x in obj):
                return [float(x) for x in obj]

            # Check if this level is all lists (higher dimension)
            if all(isinstance(x, list) for x in obj):
                results: list[float] = []
                first_result = None

                for item in obj:
                    flattened = _flatten_recursive(item, depth + 1)
                    if flattened is None:
                        return None

                    # Ensure all sublists flatten to same length (rectangular tensor)
                    if first_result is None:
                        first_result = len(flattened)
                    elif len(flattened) != first_result:
                        return None

                    results.extend(flattened)
                return results

            # Mixed types - not a valid tensor
            return None

        return _flatten_recursive(lst)

    def _extract_sequence(self, structure: Any) -> str:
        from Bio.PDB.Polypeptide import PPBuilder

        ppb = PPBuilder()  # type: ignore[no-untyped-call]  # biopython PPBuilder ctor is untyped
        seqs = []
        for pp in ppb.build_peptides(  # type: ignore[no-untyped-call]  # biopython build_peptides is untyped
            structure
        ):
            seqs.append(str(pp.get_sequence()))
        return "".join(seqs)

    def _compare_generated_seq(self, path: list[Any], value1: str, value2: str) -> None:
        # NOTE: eventually add more logic here to compare generated sequences
        if len(value1) == len(value2):
            diff = 0.0
        else:
            print(
                f">>> Generated sequence at {self._diff_path_str(path)} is different length from expected."
            )
            diff = self._inf_diff
        self._update_max_diff(diff, path, (value1, value2))

    def _compare_default(self, path: list[Any], value1: Any, value2: Any) -> None:
        if value1 == value2:
            diff = 0.0
        else:
            print(f">>> Values at {self._diff_path_str(path)} are different.")
            diff = self._inf_diff
        self._update_max_diff(diff, path, (value1, value2))

    def _update_max_diff(
        self, diff: float, path: list[Any], values: tuple[Any, Any]
    ) -> None:
        if diff > self.max_diff:
            self.max_diff = diff
            self.max_diff_path = path
            self.max_diff_values = values

    def _print_difference_details(self) -> None:
        if self.max_diff_path:
            value1, value2 = self.max_diff_values
            max_diff = (
                self.max_diff if self.max_diff != self._inf_diff else "See notes above!"
            )

            print(
                f"Max difference found at {self._diff_path_str(self.max_diff_path)}:\n"
                f"Values:\n"
                f"    {self._red_start}{self._truncate_str(value1)}{self._red_end}\n"
                f"    vs\n"
                f"    {self._red_start}{self._truncate_str(value2)}{self._red_end}\n"
                f"Max difference: {self._red_start}{max_diff}{self._red_end}"
            )

    def _diff_path_str(self, path: list[Any]) -> str:
        diff_path = " -> ".join(map(str, path))
        return f"'{self._red_start}{diff_path}{self._red_end}'"

    def _truncate_str(self, value: Any, max_length: int = 50) -> str:
        value_str = str(value)
        if len(value_str) > max_length:
            half_len = max_length // 2
            return f"{value_str[:half_len]}...[truncated]...{value_str[-half_len:]}"
        return value_str

    def format_error_message(self) -> str:
        """
        Format a detailed error message for test failures.

        Returns a multi-line string with:
        - Max difference value and location
        - Expected and actual values (truncated for readability)

        Used by the test runner to generate informative pytest.fail() messages.
        """
        if not self.max_diff_path:
            return "Actual output does not match expected (no specific difference captured)."

        # Truncate path for readability (list representation can be long)
        path_str = str(self.max_diff_path)
        truncated_path = path_str[:100] + "..." if len(path_str) > 100 else path_str

        # max_diff_values is (dict1_val, dict2_val) where dict1=actual, dict2=expected
        # (compare() is called as compare(actual_output, expected_output) in runner.py)
        actual_val = str(self.max_diff_values[0])
        actual_val = actual_val[:200] + "..." if len(actual_val) > 200 else actual_val

        expected_val = str(self.max_diff_values[1])
        expected_val = (
            expected_val[:200] + "..." if len(expected_val) > 200 else expected_val
        )

        # Format max_diff (handle infinity case)
        if self.max_diff == self._inf_diff:
            diff_str = "∞ (structural mismatch)"
        else:
            diff_str = f"{self.max_diff:.6f}"

        return (
            f"Actual output does not match expected.\n"
            f"  - Max Difference: {diff_str} at path: {truncated_path}\n"
            f"  - Expected Value: {expected_val}\n"
            f"  - Actual Value: {actual_val}"
        )


# Now the dicts_are_close function
def compare_outputs(
    dict1: dict[Any, Any],
    dict2: dict[Any, Any],
    rel_tol: float = 1e-5,
    abs_tol: Optional[float] = None,
    ignore_paths: Optional[set[str]] = None,
    cosine_distance_threshold: Optional[float] = None,
    pdb_rmsd_threshold: Optional[float] = None,
    pdb_seq_match: bool = False,
    is_generated_seq: bool = False,
    msa_content_len_threshold: Optional[float] = None,
) -> bool:
    """
    Checks if two dictionaries are close enough.
    - Specifically checks if floating-point numbers in the dictionaries are
      close within a specified tolerance.
    - If there are numeric vectors/matrices, checks if cosine distance is below the threshold.
    - If there are pdb strings in the dictionaries, checks if the RMSD between
      the two structures is less than the specified threshold.
    - If there are MSA strings, checks if lengths are within the relative threshold.
    - If there are generated sequences in the dictionaries, checks if the
      sequences are the same length.
    """

    # Perform the comparison
    comparator = DictComparator(
        rel_tol=rel_tol,
        abs_tol=abs_tol,
        ignore_paths=ignore_paths,
        cosine_distance_threshold=cosine_distance_threshold,
        pdb_rmsd_threshold=pdb_rmsd_threshold,
        pdb_seq_match=pdb_seq_match,
        is_generated_seq=is_generated_seq,
        msa_content_len_threshold=msa_content_len_threshold,
    )
    are_close = comparator.compare(dict1, dict2)

    if not are_close:
        comparator._print_difference_details()

    return are_close
