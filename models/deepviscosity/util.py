"""
DeepViscosity utility functions for data processing.

This module implements:
1. Feature scaling (StandardScaler for DeepSP features)
2. ANARCI sequence alignment with IMGT numbering
3. Sequence preprocessing to fixed-length representation
4. One-hot encoding for CNN input
"""

import subprocess
import tempfile
from pathlib import Path

from models.commons.core.logging import get_logger

logger = get_logger(__name__)

# =============================================================================
# Feature Scaling (StandardScaler for DeepSP Features)
# =============================================================================

# Embedded StandardScaler parameters extracted from DeepViscosity_scaler.joblib
# Source: https://github.com/Lailabcode/DeepViscosity
# These are the mean_, var_, and scale_ arrays for a StandardScaler trained on 229 samples
# with 30 DeepSP features. Embedding directly avoids sklearn version compatibility issues.
SCALER_PARAMS = {
    "n_features_in_": 30,
    "n_samples_seen_": 229,
    "mean_": [
        3.459563318777293,
        3.8413100436681225,
        13.91759825327511,
        3.150698689956332,
        2.932096069868996,
        6.1255458515283845,
        33.863144104803496,
        58.39903930131005,
        41.593187772925766,
        100.31506550218342,
        43.37563318777293,
        39.514803493449776,
        84.70694323144104,
        71.32550218340612,
        22.89165938864629,
        85.54445414847162,
        359.72558951965067,
        493.34834061135365,
        447.18270742358084,
        941.9816157205241,
        44.775545851528385,
        23.198646288209606,
        70.16013100436682,
        54.80650655021834,
        60.3317903930131,
        58.91410480349345,
        308.51991266375546,
        1150.9005240174672,
        1053.0090829694325,
        2179.8990829694326,
    ],
    "var_": [
        7.363354394462348,
        24.962011384222265,
        43.10204969012795,
        4.375956717072519,
        4.996950191643943,
        7.220305924753532,
        118.23347395739975,
        88.24365846570433,
        43.02083568963215,
        161.07293591274004,
        1148.6519433763656,
        1135.514658149158,
        4224.255264891974,
        1662.1364492019602,
        481.3142854560363,
        1395.9072718636187,
        18474.995449979982,
        26014.291337857783,
        13569.63850009344,
        48685.757024027,
        553.5332019946225,
        673.0797496958487,
        3035.183226620393,
        1662.4068655250665,
        1075.0533334757156,
        2097.5026512728596,
        15695.196603485821,
        18134.343607585666,
        20649.101843263856,
        51350.841718373034,
    ],
    "scale_": [
        2.713550145927351,
        4.9961996941898015,
        6.5652151290058995,
        2.091878752956901,
        2.235385915595771,
        2.6870626946079117,
        10.873521690666726,
        9.393809582150595,
        6.559027038336719,
        12.691451292611891,
        33.891768076870314,
        33.697398388438806,
        64.99427101592858,
        40.7693076860763,
        21.938876121078682,
        37.361842458096454,
        135.92275545316164,
        161.28946443539883,
        116.48879130668942,
        220.64849200487865,
        23.52728632874226,
        25.94378055904437,
        55.09249700839845,
        40.77262397154574,
        32.78800593930219,
        45.79850053520158,
        125.28047175631892,
        134.66381699471341,
        143.6979535110499,
        226.60724109871916,
    ],
}


def load_scaler():
    """Reconstruct StandardScaler from embedded parameters.

    Returns:
        sklearn.preprocessing.StandardScaler configured with pre-trained parameters
    """
    import numpy as np
    from sklearn.preprocessing import StandardScaler

    logger.info("  Reconstructing scaler from embedded parameters...")
    scaler = StandardScaler()
    scaler.n_features_in_ = SCALER_PARAMS["n_features_in_"]
    scaler.n_samples_seen_ = SCALER_PARAMS["n_samples_seen_"]
    scaler.mean_ = np.array(SCALER_PARAMS["mean_"], dtype=np.float64)
    scaler.var_ = np.array(SCALER_PARAMS["var_"], dtype=np.float64)
    scaler.scale_ = np.array(SCALER_PARAMS["scale_"], dtype=np.float64)
    logger.info("  Scaler reconstructed successfully")
    return scaler


# =============================================================================
# Sequence Alignment and Preprocessing
# =============================================================================

# IMGT positions to include for heavy chain (145 positions)
# NOTE: This list intentionally includes only specific insertion codes (111A-H, 112A-I)
# matching the original DeepViscosity training data. The DeepSP CNN models expect
# exactly (272, 21) input shape. Other IMGT insertions (e.g., 27A, 52A, 71A) are
# converted to gaps, which matches the original implementation. Do NOT add more
# positions without retraining the CNN models.
H_INCLUSION_LIST = [
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
    "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
    "21", "22", "23", "24", "25", "26", "27", "28", "29", "30",
    "31", "32", "33", "34", "35", "36", "37", "38", "39", "40",
    "41", "42", "43", "44", "45", "46", "47", "48", "49", "50",
    "51", "52", "53", "54", "55", "56", "57", "58", "59", "60",
    "61", "62", "63", "64", "65", "66", "67", "68", "69", "70",
    "71", "72", "73", "74", "75", "76", "77", "78", "79", "80",
    "81", "82", "83", "84", "85", "86", "87", "88", "89", "90",
    "91", "92", "93", "94", "95", "96", "97", "98", "99", "100",
    "101", "102", "103", "104", "105", "106", "107", "108", "109", "110",
    "111", "111A", "111B", "111C", "111D", "111E", "111F", "111G", "111H",
    "112I", "112H", "112G", "112F", "112E", "112D", "112C", "112B", "112A", "112",
    "113", "114", "115", "116", "117", "118", "119", "120",
    "121", "122", "123", "124", "125", "126", "127", "128",
]  # fmt: skip

# IMGT positions to include for light chain (127 positions)
# NOTE: Same as heavy chain - this fixed representation matches the original training.
# Insertions not in this list (e.g., 30A, 49A, 95A) become gaps by design.
L_INCLUSION_LIST = [
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
    "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
    "21", "22", "23", "24", "25", "26", "27", "28", "29", "30",
    "31", "32", "33", "34", "35", "36", "37", "38", "39", "40",
    "41", "42", "43", "44", "45", "46", "47", "48", "49", "50",
    "51", "52", "53", "54", "55", "56", "57", "58", "59", "60",
    "61", "62", "63", "64", "65", "66", "67", "68", "69", "70",
    "71", "72", "73", "74", "75", "76", "77", "78", "79", "80",
    "81", "82", "83", "84", "85", "86", "87", "88", "89", "90",
    "91", "92", "93", "94", "95", "96", "97", "98", "99", "100",
    "101", "102", "103", "104", "105", "106", "107", "108", "109", "110",
    "111", "112", "113", "114", "115", "116", "117", "118", "119", "120",
    "121", "122", "123", "124", "125", "126", "127",
]  # fmt: skip

# Mapping from IMGT position to array index (heavy chain)
H_DICT = {pos: idx for idx, pos in enumerate(H_INCLUSION_LIST)}

# Mapping from IMGT position to array index (light chain)
L_DICT = {pos: idx for idx, pos in enumerate(L_INCLUSION_LIST)}

# One-hot encoding alphabet
AA_ALPHABET = {
    "A": 0, "C": 1, "D": 2, "E": 3, "F": 4, "G": 5, "H": 6, "I": 7, "K": 8,
    "L": 9, "M": 10, "N": 11, "P": 12, "Q": 13, "R": 14, "S": 15, "T": 16,
    "V": 17, "W": 18, "Y": 19, "-": 20,
}  # fmt: skip

# Total sequence length after alignment
H_LENGTH = 145  # Heavy chain positions
L_LENGTH = 127  # Light chain positions
TOTAL_LENGTH = H_LENGTH + L_LENGTH  # 272


def run_anarci(
    heavy_chain: str,
    light_chain: str,
    temp_dir: Path,
) -> tuple[dict, dict]:
    """
    Run ANARCI alignment on heavy and light chain sequences.

    Args:
        heavy_chain: VH sequence
        light_chain: VL sequence
        temp_dir: Temporary directory for ANARCI output files

    Returns:
        Tuple of (heavy_aligned_dict, light_aligned_dict) where each dict
        maps IMGT position to amino acid residue.
    """
    import pandas as pd

    # Write FASTA files
    h_fasta = temp_dir / "seq_H.fasta"
    l_fasta = temp_dir / "seq_L.fasta"

    h_fasta.write_text(f">query\n{heavy_chain}\n")
    l_fasta.write_text(f">query\n{light_chain}\n")

    # Run ANARCI for heavy chain
    h_output = temp_dir / "seq_aligned"
    try:
        subprocess.run(
            [
                "ANARCI",
                "-i",
                str(h_fasta),
                "-o",
                str(h_output),
                "-s",
                "imgt",
                "-r",
                "heavy",
                "--csv",
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"ANARCI heavy chain alignment failed: {e.stderr.decode()}"
        ) from e
    except FileNotFoundError:
        raise RuntimeError(
            "ANARCI not found. Please ensure ANARCI is installed."
        ) from None

    # Run ANARCI for light chain
    l_output = temp_dir / "seq_aligned"
    try:
        subprocess.run(
            [
                "ANARCI",
                "-i",
                str(l_fasta),
                "-o",
                str(l_output),
                "-s",
                "imgt",
                "-r",
                "light",
                "--csv",
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"ANARCI light chain alignment failed: {e.stderr.decode()}"
        ) from e

    # Parse aligned CSV files
    h_csv = temp_dir / "seq_aligned_H.csv"
    l_csv = temp_dir / "seq_aligned_KL.csv"

    if not h_csv.exists():
        raise RuntimeError(f"ANARCI heavy chain output not found: {h_csv}")
    if not l_csv.exists():
        raise RuntimeError(f"ANARCI light chain output not found: {l_csv}")

    h_df = pd.read_csv(h_csv)
    l_df = pd.read_csv(l_csv)

    if len(h_df) == 0:
        raise RuntimeError("ANARCI failed to align heavy chain sequence")
    if len(l_df) == 0:
        raise RuntimeError("ANARCI failed to align light chain sequence")

    # Extract first row (we only process one sequence at a time)
    h_row = h_df.iloc[0]
    l_row = l_df.iloc[0]

    # Convert to dictionaries mapping position -> residue
    h_aligned = {col: h_row[col] for col in h_df.columns if col in H_INCLUSION_LIST}
    l_aligned = {col: l_row[col] for col in l_df.columns if col in L_INCLUSION_LIST}

    return h_aligned, l_aligned


def preprocess_sequences(
    h_aligned: dict,
    l_aligned: dict,
) -> str:
    """
    Preprocess aligned sequences into fixed-length representation.

    Args:
        h_aligned: Dict mapping IMGT position to residue (heavy chain)
        l_aligned: Dict mapping IMGT position to residue (light chain)

    Returns:
        String of length 272 (145 + 127) with gaps for missing positions
    """
    import pandas as pd

    # Build heavy chain array (145 positions)
    h_seq = ["-"] * H_LENGTH
    for pos in H_INCLUSION_LIST:
        if pos in h_aligned:
            residue = h_aligned[pos]
            # Handle NaN/empty values from pandas using pd.isna()
            if pd.isna(residue) or residue in ("", "-"):
                h_seq[H_DICT[pos]] = "-"
            else:
                h_seq[H_DICT[pos]] = str(residue)

    # Build light chain array (127 positions)
    l_seq = ["-"] * L_LENGTH
    for pos in L_INCLUSION_LIST:
        if pos in l_aligned:
            residue = l_aligned[pos]
            # Handle NaN/empty values from pandas using pd.isna()
            if pd.isna(residue) or residue in ("", "-"):
                l_seq[L_DICT[pos]] = "-"
            else:
                l_seq[L_DICT[pos]] = str(residue)

    # Combine
    return "".join(h_seq) + "".join(l_seq)


def one_hot_encode(sequence: str):
    """
    One-hot encode aligned antibody sequence.

    Args:
        sequence: Aligned sequence of length 272

    Returns:
        NumPy array of shape (272, 21) with one-hot encoding
    """
    import numpy as np

    if len(sequence) != TOTAL_LENGTH:
        raise ValueError(
            f"Expected sequence length {TOTAL_LENGTH}, got {len(sequence)}"
        )

    # Create one-hot matrix
    x = np.zeros((TOTAL_LENGTH, len(AA_ALPHABET)), dtype=np.float32)

    for i, char in enumerate(sequence):
        if char in AA_ALPHABET:
            x[i, AA_ALPHABET[char]] = 1.0
        else:
            # Unknown character - treat as gap
            x[i, AA_ALPHABET["-"]] = 1.0

    return x


def align_and_encode(
    heavy_chain: str,
    light_chain: str,
):
    """
    Complete pipeline: align sequences and return one-hot encoded representation.

    Args:
        heavy_chain: VH sequence
        light_chain: VL sequence

    Returns:
        NumPy array of shape (272, 21) ready for DeepSP CNN input
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Run ANARCI alignment
        h_aligned, l_aligned = run_anarci(heavy_chain, light_chain, temp_path)

        # Preprocess to fixed-length
        aligned_seq = preprocess_sequences(h_aligned, l_aligned)

        # One-hot encode
        encoded = one_hot_encode(aligned_seq)

    return encoded
