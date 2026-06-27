"""Lightweight validators for PDB and mmCIF structure formats.

PDB (Protein Data Bank) format:
- Legacy format from 1970s with fixed 80-column width
- ATOM/HETATM records store atomic coordinates in columns 31-38 (X), 39-46 (Y), 47-54 (Z)
- Limited to 99,999 atoms and 62 chains
- Still widely used despite limitations

mmCIF (macromolecular Crystallographic Information File) format:
- Modern replacement for PDB format, standard since 2014
- Extension of CIF format specifically for biological macromolecules
- No size limitations, uses key-value pairs and tabular loops
- Uses _atom_site.* fields for atomic data (e.g., _atom_site.Cartn_x/y/z for coordinates)
- Also known as PDBx/mmCIF

Note: "CIF" in structural biology contexts typically means mmCIF, not general CIF format.
"""


def _reject_non_pdb_formats(text: str) -> None:
    """Check and reject obvious non-PDB formats."""
    stripped = text.strip()
    if stripped.startswith(("{", "[", "<", "data_")):
        raise ValueError("Input appears to be JSON, XML, or CIF format, not PDB")


def _validate_pdb_coordinates(line: str, x_str: str, y_str: str, z_str: str) -> bool:
    """Validate that coordinate strings are numeric."""
    if not (x_str and y_str and z_str):
        raise ValueError("ATOM/HETATM record has missing coordinates")

    try:
        float(x_str)
        float(y_str)
        float(z_str)
        return True
    except ValueError as e:
        raise ValueError(
            f"ATOM/HETATM record has non-numeric coordinates: "
            f"X='{x_str}', Y='{y_str}', Z='{z_str}'"
        ) from e


def _validate_atom_hetatm_line(line: str) -> bool:
    """Validate an ATOM or HETATM line structure and coordinates."""
    if len(line) < 54:
        raise ValueError(
            f"ATOM/HETATM line too short ({len(line)} chars), "
            f"must be at least 54 chars for coordinates"
        )

    # Extract and validate coordinates
    x_str = line[30:38].strip()
    y_str = line[38:46].strip()
    z_str = line[46:54].strip()

    return _validate_pdb_coordinates(line, x_str, y_str, z_str)


def _get_pdb_record_types() -> set[str]:
    """Return the set of valid PDB record types."""
    return {
        "ATOM",
        "HETATM",
        "ANISOU",
        "TER",
        "END",
        "HELIX",
        "SHEET",
        "TURN",
        "SSBOND",
        "LINK",
        "CISPEP",
        "SITE",
        "CRYST1",
        "ORIGX1",
        "ORIGX2",
        "ORIGX3",
        "SCALE1",
        "SCALE2",
        "SCALE3",
        "MTRIX1",
        "MTRIX2",
        "MTRIX3",
        "MODEL",
        "ENDMDL",
        "CONECT",
        "MASTER",
        "SEQRES",
        "MODRES",
        "HET",
        "HETNAM",
        "HETSYN",
        "FORMUL",
        "REMARK",
        "DBREF",
        "SEQADV",
        "TITLE",
        "COMPND",
        "SOURCE",
        "KEYWDS",
        "EXPDTA",
        "AUTHOR",
        "REVDAT",
        "JRNL",
        "HEADER",
        "OBSLTE",
        "SPRSDE",
        "NUMMDL",
        "MDLTYP",
        "CAVEAT",
    }


def _process_pdb_line(line: str, valid_record_types: set) -> tuple[bool, bool, bool]:
    """Process a single PDB line.
    Returns (is_atom_hetatm, has_valid_record, has_valid_coords)."""
    if len(line) < 6:
        return False, False, False

    record_check = line[:6].rstrip()

    if record_check in {"ATOM", "HETATM"}:
        valid_coords = _validate_atom_hetatm_line(line)
        return True, True, valid_coords

    return False, record_check in valid_record_types, False


def _validate_pdb_content(lines: list[str]) -> tuple[int, bool]:
    """Validate PDB content and return (valid_atom_count, has_valid_records)."""
    valid_record_types = _get_pdb_record_types()
    valid_atom_count = 0
    has_valid_records = False
    has_atom_or_hetatm = False

    for line in lines:
        if not line:
            continue

        is_atom, is_valid, has_valid_coords = _process_pdb_line(
            line, valid_record_types
        )

        if is_atom:
            has_atom_or_hetatm = True
            if has_valid_coords:
                valid_atom_count += 1
        if is_valid:
            has_valid_records = True

    if not has_atom_or_hetatm:
        raise ValueError("PDB file must contain at least one ATOM or HETATM record")

    if not has_valid_records:
        raise ValueError(
            "No valid PDB record types found. File does not appear to be PDB format"
        )

    return valid_atom_count, has_valid_records


def validate_pdb(text: str) -> str:
    """Validate PDB format structure content with lightweight checks."""
    if not text or not text.strip():
        raise ValueError("PDB content cannot be empty")

    _reject_non_pdb_formats(text)

    lines = text.splitlines()
    if not lines:
        raise ValueError("PDB content must contain at least one line")

    valid_atom_count, _ = _validate_pdb_content(lines)

    if valid_atom_count < 1:
        raise ValueError(
            "PDB file must contain at least one ATOM or HETATM record with valid coordinates"
        )

    return text


def _reject_non_cif_formats(text: str) -> None:
    """Check and reject obvious non-CIF formats."""
    if text.startswith(("{", "[", "<", "<?xml", "<!DOCTYPE")):
        raise ValueError("Input appears to be JSON or XML format, not mmCIF")

    if text.startswith(("ATOM", "HETATM", "REMARK", "HEADER")):
        raise ValueError("Input appears to be PDB format, not mmCIF")


def _scan_cif_atom_fields(lines: list[str], start_idx: int) -> tuple[set[str], int]:
    """Scan for _atom_site fields and return (fields, end_index)."""
    atom_fields = set()
    j = start_idx
    while j < len(lines) and lines[j].strip().startswith("_"):
        field = lines[j].strip().split()[0]
        if "_atom_site." in field:
            atom_fields.add(field)
        j += 1
    return atom_fields, j


def _count_atom_data_rows(lines: list[str], start_idx: int) -> int:
    """Count actual data rows after atom_site field definitions."""
    data_rows = 0
    j = start_idx

    while j < len(lines):
        data_line = lines[j].strip()

        # Skip empty lines and comments
        if not data_line or data_line.startswith("#"):
            j += 1
            continue

        # Stop if we hit another keyword
        if (
            data_line.startswith("_")
            or data_line == "loop_"
            or data_line.startswith("data_")
        ):
            break

        # Count non-empty data rows
        if data_line.split():
            data_rows += 1
        j += 1

    return data_rows


def _process_cif_loop(lines: list[str], idx: int) -> tuple[set[str], int, int]:
    """Process a CIF loop_ section.
    Returns (atom_site_fields, atom_data_rows, next_index)."""
    fields, next_idx = _scan_cif_atom_fields(lines, idx + 1)

    if not fields:
        return set(), 0, next_idx

    data_rows = _count_atom_data_rows(lines, next_idx)
    return fields, data_rows, next_idx + data_rows


def _process_cif_key_value(line: str) -> tuple[str, bool]:
    """Process a potential _atom_site key-value pair.
    Returns (field_name, has_value)."""
    parts = line.split()
    if not parts:
        return "", False

    field_name = parts[0]
    has_value = len(parts) > 1
    return field_name, has_value


def _parse_cif_structure(lines: list[str]) -> tuple[bool, set[str], int]:
    """Parse CIF structure and extract atom_site information.
    Returns (has_data_block, atom_site_fields, atom_data_rows)."""
    has_data_block = False
    atom_site_fields = set()
    atom_data_rows = 0
    in_loop = False

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines and comments
        if not line or line.startswith("#"):
            i += 1
            continue

        # Handle data blocks
        if line.startswith("data_"):
            has_data_block = True
            in_loop = False
            i += 1
            continue

        # Handle loops
        if line == "loop_":
            in_loop = True
            fields, data_rows, next_i = _process_cif_loop(lines, i)
            if fields:
                atom_site_fields.update(fields)
                atom_data_rows += data_rows
                i = next_i - 1
            i += 1
            continue

        # Handle atom_site fields outside loops
        if "_atom_site." in line and not in_loop:
            field_name, has_value = _process_cif_key_value(line)
            if field_name:
                atom_site_fields.add(field_name)
                if has_value:
                    atom_data_rows += 1

        # Exit loop context
        elif in_loop and not line.startswith("_"):
            in_loop = False

        i += 1

    return has_data_block, atom_site_fields, atom_data_rows


def _get_critical_cif_fields() -> set[str]:
    """Return critical required fields for CIF validation."""
    return {
        "_atom_site.Cartn_x",
        "_atom_site.Cartn_y",
        "_atom_site.Cartn_z",
        "_atom_site.label_atom_id",
        "_atom_site.label_comp_id",
    }


def _get_recommended_cif_fields() -> set[str]:
    """Return recommended fields for CIF validation."""
    return {
        "_atom_site.group_PDB",
        "_atom_site.type_symbol",
        "_atom_site.label_asym_id",
    }


def _validate_cif_fields(atom_site_fields: set[str]) -> None:
    """Validate that required CIF fields are present."""
    critical_fields = _get_critical_cif_fields()
    missing_critical = critical_fields - atom_site_fields

    if missing_critical:
        raise ValueError(
            f"mmCIF file missing critical fields: {missing_critical}. "
            f"All coordinate fields (Cartn_x/y/z) and identifiers are required"
        )

    recommended_fields = _get_recommended_cif_fields()
    missing_recommended = recommended_fields - atom_site_fields

    if len(missing_recommended) == len(recommended_fields):
        raise ValueError(
            f"mmCIF file missing all recommended fields: {missing_recommended}"
        )


def _has_cif_structure(lines: list[str]) -> bool:
    """Check if file has basic CIF structural elements."""
    for line in lines:
        stripped = line.strip()
        if stripped and (
            stripped.startswith("_")
            or stripped == "loop_"
            or stripped.startswith("data_")
        ):
            return True
    return False


def validate_cif(text: str) -> str:
    """Validate mmCIF format structure content with lightweight checks."""
    normalized = text.strip()
    if not normalized:
        raise ValueError("mmCIF content cannot be empty")

    _reject_non_cif_formats(normalized)

    lines = normalized.splitlines()
    has_data_block, atom_site_fields, atom_data_rows = _parse_cif_structure(lines)

    # Validate structure
    if not has_data_block:
        raise ValueError("mmCIF file must start with a data_ block identifier")

    if not atom_site_fields:
        raise ValueError("mmCIF file must contain _atom_site records")

    if atom_data_rows < 1:
        raise ValueError(
            "mmCIF file has _atom_site fields but no actual atom data rows"
        )

    # Validate required fields
    _validate_cif_fields(atom_site_fields)

    # Final structure check
    if not _has_cif_structure(lines):
        raise ValueError(
            "File does not appear to be valid mmCIF format - "
            "missing CIF structural elements"
        )

    return normalized
