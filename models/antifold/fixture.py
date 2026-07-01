from urllib.error import URLError
from urllib.request import urlopen

from models.antifold.config import MODEL_FAMILY, antifold_commit_hash
from models.antifold.schema import (
    AntiFoldBaseRequestItem,
    AntiFoldEncodeIncludeOptions,
    AntiFoldEncodeRequest,
    AntiFoldEncodeRequestParams,
    AntiFoldGenerateRequest,
    AntiFoldGenerateRequestParams,
    AntiFoldPredictRequest,
    AntiFoldPredictRequestParams,
)
from models.commons.core.logging import get_logger
from models.commons.model.schema import ModelActions
from models.commons.testing.config import ActionTestCase, TestSuite, VariantTestMapping
from models.commons.testing.fixture import FixtureGenerator

logger = get_logger(__name__)

# Test input/output filenames

# Encode test cases
ENCODE_3HFM_INPUT = "3hfm_encode_input.json"
ENCODE_3HFM_OUTPUT = "3hfm_encode_expected_output.json"
ENCODE_8OI2_INPUT = "8oi2_imgt_encode_input.json"
ENCODE_8OI2_OUTPUT = "8oi2_imgt_encode_expected_output.json"

# Predict log prob and score test cases (share same input)
LOGPROB_3HFM_INPUT = "3hfm_logprob_input.json"
LOGPROB_3HFM_OUTPUT = "3hfm_logprob_expected_output.json"
SCORE_3HFM_OUTPUT = "3hfm_score_expected_output.json"

# Generate test cases
GENERATE_3HFM_INPUT = "3hfm_generate_input.json"
GENERATE_3HFM_OUTPUT = "3hfm_generate_expected_output.json"
GENERATE_8OI2_INPUT = "8oi2_imgt_generate_input.json"
GENERATE_8OI2_OUTPUT = "8oi2_imgt_generate_expected_output.json"
GENERATE_6Y1L_INPUT = "6y1l_imgt_generate_input.json"
GENERATE_6Y1L_OUTPUT = "6y1l_imgt_generate_expected_output.json"

# --- Fixture generation (self-contained; no pre-existing R2 inputs required) ---
#
# AntiFold is antibody-specific *inverse folding*: its input is a 3D backbone
# structure (PDB), not a sequence. Region-based sampling (CDR1/CDR2/CDR3/...)
# is defined over IMGT antibody numbering (see antifold/external/antiscripts.py
# IMGT_dict / get_imgt_mask), so the input PDBs must already be IMGT-numbered
# for `generate` region selection to be meaningful — a plain structure fetched
# fresh from RCSB would not carry that numbering.
#
# Rather than invent our own IMGT renumbering here, we fetch the exact example
# PDBs bundled in the upstream AntiFold repo (pinned to the same commit already
# used to build the model image, see `antifold_commit_hash` in config.py). These
# are the canonical inputs the upstream project itself uses to demonstrate each
# chain-configuration mode, so they are known-good for this model:
#   - data/antibody_antigen/3hfm.pdb   -- paired VH/VL + antigen (H, L, Y)
#   - data/nanobody/8oi2_imgt.pdb      -- nanobody / heavy-chain-only (B), IMGT-numbered
#   - data/pdbs/6y1l_imgt.pdb          -- paired VH/VL (H, L), IMGT-numbered
# (See upstream README.md "Run AntiFold" examples for the exact chain args used
# with each file.)

_ANTIFOLD_RAW_BASE = (
    f"https://raw.githubusercontent.com/oxpig/AntiFold/{antifold_commit_hash}"
)


def _download_pdb(repo_relative_path: str) -> str:
    """Download a canonical example PDB from the pinned upstream AntiFold repo."""
    url = f"{_ANTIFOLD_RAW_BASE}/{repo_relative_path}"
    try:
        with urlopen(url, timeout=10) as response:
            raw_bytes: bytes = response.read()
            return raw_bytes.decode("utf-8")
    except URLError as e:
        raise ValueError(f"Failed to download PDB from {url}: {e}") from e


# TestSuite skeleton — test cases are built lazily inside generate() to avoid
# module-scope network calls (GitHub PDB downloads) that would break
# --collect-only / import-time behavior.
fixture_generation_suite = TestSuite(
    model_family=MODEL_FAMILY,
    r2_fixture_subdir="models",
    variant_test_mappings=[
        VariantTestMapping(
            variant_config={},  # Single variant model - applies to all
            test_cases=[],  # populated by generate()
        )
    ],
)


def generate() -> None:
    """Configures and runs the fixture generator for the antifold model."""
    logger.info("Downloading canonical example PDBs from the AntiFold repo...")
    # 3HFM: HyHel-10 Fab / hen-egg-lysozyme antibody-antigen complex.
    # Chains: H (heavy), L (light), Y (antigen).
    pdb_3hfm = _download_pdb("data/antibody_antigen/3hfm.pdb")
    # 8OI2: ALB1 megabody (nanobody scaffold) bound to human serum albumin,
    # IMGT-renumbered. Chains: A (antigen/albumin), B (nanobody/VHH).
    pdb_8oi2_imgt = _download_pdb("data/nanobody/8oi2_imgt.pdb")
    # 6Y1L: paired VH/VL Fab fragment, IMGT-renumbered. Chains: H, L.
    pdb_6y1l_imgt = _download_pdb("data/pdbs/6y1l_imgt.pdb")
    logger.info("Downloaded all example PDBs successfully.")

    # Rebuild test cases with the freshly downloaded PDBs.
    fixture_generation_suite.variant_test_mappings[0].test_cases = [
        # --- encode ---
        # Antibody-antigen complex; ask for both mean-pooled embeddings and
        # per-position logits to exercise more of the response schema.
        ActionTestCase(
            action_name=ModelActions.ENCODE,
            input_fixture=AntiFoldEncodeRequest(
                params=AntiFoldEncodeRequestParams(
                    heavy_chain_id="H",
                    light_chain_id="L",
                    antigen_chain_id="Y",
                    include=[
                        AntiFoldEncodeIncludeOptions.MEAN,
                        AntiFoldEncodeIncludeOptions.LOGITS,
                    ],
                ),
                items=[AntiFoldBaseRequestItem(pdb=pdb_3hfm)],
            ),
            input_filename_template=ENCODE_3HFM_INPUT,
            expected_output_fixture=ENCODE_3HFM_OUTPUT,
            tolerances={"rel_tol": 3e-4, "cosine_distance_threshold": 0.02},
        ),
        # Nanobody / heavy-chain-only mode; default include=["mean"].
        ActionTestCase(
            action_name=ModelActions.ENCODE,
            input_fixture=AntiFoldEncodeRequest(
                params=AntiFoldEncodeRequestParams(heavy_chain_id="B"),
                items=[AntiFoldBaseRequestItem(pdb=pdb_8oi2_imgt)],
            ),
            input_filename_template=ENCODE_8OI2_INPUT,
            expected_output_fixture=ENCODE_8OI2_OUTPUT,
            tolerances={"rel_tol": 3e-4, "cosine_distance_threshold": 0.02},
        ),
        # --- log_prob / score (share the same input) ---
        ActionTestCase(
            action_name=ModelActions.LOG_PROB,
            input_fixture=AntiFoldPredictRequest(
                params=AntiFoldPredictRequestParams(
                    heavy_chain_id="H",
                    light_chain_id="L",
                    antigen_chain_id="Y",
                ),
                items=[AntiFoldBaseRequestItem(pdb=pdb_3hfm)],
            ),
            input_filename_template=LOGPROB_3HFM_INPUT,
            expected_output_fixture=LOGPROB_3HFM_OUTPUT,
            tolerances={"rel_tol": 1e-4},
        ),
        ActionTestCase(
            action_name=ModelActions.SCORE,
            input_fixture=LOGPROB_3HFM_INPUT,  # Reuse the already-written input file
            expected_output_fixture=SCORE_3HFM_OUTPUT,
            tolerances={"rel_tol": 1e-4},
        ),
        # --- generate ---
        # Paired VH/VL + antigen context, default regions (CDR1/CDR2/CDR3).
        ActionTestCase(
            action_name=ModelActions.GENERATE,
            input_fixture=AntiFoldGenerateRequest(
                params=AntiFoldGenerateRequestParams(
                    heavy_chain_id="H",
                    light_chain_id="L",
                    antigen_chain_id="Y",
                    seed=42,
                    num_seq_per_target=3,
                    sampling_temp=0.2,
                ),
                items=[AntiFoldBaseRequestItem(pdb=pdb_3hfm)],
            ),
            input_filename_template=GENERATE_3HFM_INPUT,
            expected_output_fixture=GENERATE_3HFM_OUTPUT,
        ),
        # Nanobody / heavy-chain-only mode.
        ActionTestCase(
            action_name=ModelActions.GENERATE,
            input_fixture=AntiFoldGenerateRequest(
                params=AntiFoldGenerateRequestParams(
                    heavy_chain_id="B",
                    seed=42,
                    num_seq_per_target=3,
                    sampling_temp=0.2,
                ),
                items=[AntiFoldBaseRequestItem(pdb=pdb_8oi2_imgt)],
            ),
            input_filename_template=GENERATE_8OI2_INPUT,
            expected_output_fixture=GENERATE_8OI2_OUTPUT,
        ),
        # Paired VH/VL, no antigen context.
        ActionTestCase(
            action_name=ModelActions.GENERATE,
            input_fixture=AntiFoldGenerateRequest(
                params=AntiFoldGenerateRequestParams(
                    heavy_chain_id="H",
                    light_chain_id="L",
                    seed=42,
                    num_seq_per_target=3,
                    sampling_temp=0.2,
                ),
                items=[AntiFoldBaseRequestItem(pdb=pdb_6y1l_imgt)],
            ),
            input_filename_template=GENERATE_6Y1L_INPUT,
            expected_output_fixture=GENERATE_6Y1L_OUTPUT,
        ),
    ]

    generator = FixtureGenerator(fixture_generation_suite)
    generator.generate()


if __name__ == "__main__":
    generate()

# Run with: python models/antifold/fixture.py
