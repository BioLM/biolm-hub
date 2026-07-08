"""A3M file processing utilities.

Functions for parsing, combining, and writing A3M (Multiple Sequence Alignment)
files used in protein structure prediction pipelines.
"""

from collections import OrderedDict


def combine_a3ms(
    a3m_contents: list[str], output_path: str, keep_first_query_only: bool = True
) -> None:
    """
    Combine multiple A3M file contents into one file.

    This function merges multiple A3M alignment files while optionally keeping
    only the first query sequence to avoid redundancy.

    Args:
        a3m_contents: List of A3M file contents as strings
        output_path: Path where to write the combined A3M file
        keep_first_query_only: If True, keeps only the query sequence from the
                              first A3M file, discarding query sequences from
                              subsequent files
    """
    all_entries = _collect_unique_a3m_entries(a3m_contents, keep_first_query_only)
    _write_combined_a3m_file(all_entries, output_path)


def _collect_unique_a3m_entries(
    a3m_contents: list[str], keep_first_query_only: bool
) -> OrderedDict[str, tuple[str, str]]:
    """Extract all unique entries from A3M contents."""
    all_entries: OrderedDict[str, tuple[str, str]] = OrderedDict()

    for idx, a3m_str in enumerate(a3m_contents):
        entries = _parse_a3m_string(a3m_str)
        for i, (header, seq) in enumerate(entries):
            # Skip query sequences from all files except the first one
            if idx > 0 and keep_first_query_only and i == 0:
                continue

            # Use sequence as key for deduplication
            if seq not in all_entries:
                all_entries[seq] = (header, seq)

    return all_entries


def _parse_a3m_string(a3m_str: str) -> list[tuple[str, str]]:
    """Parse A3M string content into header-sequence pairs."""
    lines = a3m_str.splitlines()
    entries: list[tuple[str, str]] = []
    current_header = None
    current_seq: list[str] = []

    for line in lines:
        line = line.strip()
        if line.startswith(">"):
            if current_header is not None:
                entries.append((current_header, "".join(current_seq)))
            current_header = line
            current_seq = []
        else:
            current_seq.append(line)

    if current_header is not None:
        entries.append((current_header, "".join(current_seq)))

    return entries


def _write_combined_a3m_file(
    all_entries: OrderedDict[str, tuple[str, str]], output_path: str
) -> None:
    """Write combined A3M entries to file."""
    with open(output_path, "w") as f:
        for header, seq in all_entries.values():
            f.write(f"{header}\n{seq}\n")
