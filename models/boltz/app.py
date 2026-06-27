import collections
import json
import multiprocessing
import os
import subprocess
import tempfile
import threading
from functools import lru_cache
from pathlib import Path

import modal
import numpy as np
import yaml

# Boltz-specific imports
from models.boltz.config import MODEL_FAMILY
from models.boltz.download import get_model_dir
from models.boltz.schema import (
    Boltz1PredictRequest,
    Boltz2PredictRequest,
    BoltzAffinityScores,
    BoltzAlignmentDatabase,
    BoltzConfidenceScores,
    BoltzEmbeddings,
    BoltzEntity,
    BoltzEntityType,
    BoltzIncludeParams,
    BoltzModelParams,
    BoltzModelVersion,
    BoltzPredictResponse,
    BoltzPredictResponseOutput,
    MSASearchMode,
)
from models.boltz.utils import (
    calculate_ipae,
    calculate_ipsae,
    construct_yaml_data,
    parse_structure_from_cif,
)
from models.commons.billing.mixin import BillingMixinSnap
from models.commons.core.decorator import modal_endpoint
from models.commons.core.error import UserError
from models.commons.data.validator import validate_smiles_with_rdkit
from models.commons.modal.deployment import run_or_deploy_modal_app
from models.commons.modal.downloader import setup_download_layer
from models.commons.modal.source import setup_source_layer
from models.commons.model.config import biolm_model_class
from models.commons.util.config import (
    cloudflare_r2_secret,
    common_requirements,
    redis_url_secret,
)
from models.commons.util.device import get_torch_device
from models.commons.util.environment import parse_variant

# Parse variant configuration
variant_config = parse_variant(
    env_var_name="MODEL_VERSION",
    allowed_values=BoltzModelVersion,
    default=BoltzModelVersion.BOLTZ2,
)
model_version = variant_config["MODEL_VERSION"]

# Conditional type based on model version
if model_version == BoltzModelVersion.BOLTZ1:
    BoltzPredictRequestType = Boltz1PredictRequest
else:
    BoltzPredictRequestType = Boltz2PredictRequest

image = modal.Image.from_registry("pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime")
# Setup download layer with model weights
image = setup_download_layer(
    image,
    base_model_slug=BoltzModelParams.base_model_slug,
    params_version=BoltzModelParams.params_version,
    variant_config=variant_config,
)
# Add dependencies and packages
image = (
    image.apt_install("git", "build-essential", "procps").uv_pip_install(
        common_requirements
    )  # procps for computing container uptime
    # Install boltz WITHOUT [cuda] extras. The [cuda] extra pulls floating
    # cuequivariance deps that upgrade torch from 2.6.0+cu124 to 2.11.0+cu130,
    # breaking CUDA (libnvrtc-builtins.so.13.0 missing in the 12.4 container).
    # Use --no_kernels in CLI to skip cuequivariance kernel paths at runtime.
    .uv_pip_install(
        "pytorch-lightning==2.5.0",
        "torchmetrics==1.4.0",
        "boltz==2.2.0",
    )
)
# Finally, add all model files
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)

# Define the app using unified config
app_name, modal_resource_spec = MODEL_FAMILY.get_app_config(**variant_config)
print(f"App name: {app_name}")
app = modal.App(app_name, image=image)

# Define the Modal volume for mols (needed for Boltz2)
boltz2_mols_vol_name = "boltz2-mols-vol"
boltz2_mols_vol = modal.Volume.from_name(boltz2_mols_vol_name, create_if_missing=True)

# ---------------------------------------------------------------------------
# MSA Search NIM integration helpers
# ---------------------------------------------------------------------------

# Mapping from MSA Search NIM database names to Boltz alignment database names.
# The NIM may label databases using biological names (uniref90, mgnify, bfd) or
# workspace names (uniref30, colabfold_envdb).  Map both conventions so the
# integration works regardless of NIM version or variant.
_MSA_DB_TO_BOLTZ: dict[str, BoltzAlignmentDatabase] = {
    # Biological database names (standard NIM output)
    "uniref90": BoltzAlignmentDatabase.UNIREF90,
    "mgnify": BoltzAlignmentDatabase.MGNIFY,
    "bfd": BoltzAlignmentDatabase.SMALL_BFD,
    "small_bfd": BoltzAlignmentDatabase.SMALL_BFD,
    # Workspace/ColabFold database names (alternative NIM labeling).
    # Note: uniref30 (30% identity) differs from uniref90 (90% identity) but Boltz
    # merges all a3m content via combine_a3ms() regardless of key, so the enum
    # value is only a label -- it does not affect prediction quality.
    "uniref30": BoltzAlignmentDatabase.UNIREF90,
    "colabfold_envdb": BoltzAlignmentDatabase.SMALL_BFD,
}

# MSA Search NIM deployed app names (from models/msa_search_nim/config.py)
_MSA_SEARCH_APP_NAMES: dict[MSASearchMode, str] = {
    MSASearchMode.FAST: "msa-search-nim-fast",
    MSASearchMode.STANDARD: "msa-search-nim",
}


@lru_cache(maxsize=4)
def _get_msa_search_cls(msa_mode: MSASearchMode):
    """Cache the expensive ``modal.Cls.from_name`` lookup (keyed by mode only)."""
    nim_app_name = _MSA_SEARCH_APP_NAMES[msa_mode]
    return modal.Cls.from_name(nim_app_name, "MSASearchService")


def _get_msa_search_service(msa_mode: MSASearchMode, app_username: str):
    """Get an MSA Search NIM service instance for the given user.

    The ``Cls.from_name`` lookup is cached; only instance creation (cheap)
    varies per ``app_username``.
    """
    MSASearchService = _get_msa_search_cls(msa_mode)
    return MSASearchService(app_username=app_username)


def _extract_alignments_from_nim_result(
    nim_result_alignments: dict,
) -> dict[BoltzAlignmentDatabase, str]:
    """Extract a3m alignment strings from a single NIM result's alignments dict.

    The NIM response structure for alignments is::

        {
            "uniref90": {"a3m": {"format": "a3m", "alignment": ">query\\n..."}},
            "mgnify":   {"a3m": {"format": "a3m", "alignment": ">query\\n..."}},
            ...
        }

    Returns a dict mapping ``BoltzAlignmentDatabase`` enum values to raw a3m
    strings, suitable for assignment to ``BoltzEntity.alignment``.
    """
    boltz_alignments: dict[BoltzAlignmentDatabase, str] = {}
    for db_name, formats in nim_result_alignments.items():
        boltz_db = _MSA_DB_TO_BOLTZ.get(db_name)
        if boltz_db is None:
            # Skip databases not in the mapping (e.g. pdb70, pdb100)
            continue
        # Prefer a3m format
        a3m_data = formats.get("a3m")
        if a3m_data and a3m_data.get("alignment"):
            # Prefer higher-quality databases: skip if we already have this
            # Boltz DB from a more specific source (e.g. uniref90 over uniref30)
            if boltz_db not in boltz_alignments:
                boltz_alignments[boltz_db] = a3m_data["alignment"]
    return boltz_alignments


def _generate_msa_for_entities(
    molecules: list[BoltzEntity],
    msa_mode: MSASearchMode,
    app_username: str,
) -> None:
    """Generate MSA alignments for protein entities that lack user-provided alignments.

    Mutates ``entity.alignment`` in-place for each qualifying protein entity.
    Uses ``encode()`` for single-protein inputs and ``encode_paired()`` for
    multi-protein complexes (2-8 chains).

    On failure, logs a warning and falls back to empty MSA (Boltz will use
    ``msa: empty`` for entities without alignments).
    """
    # Identify protein entities that need MSA
    proteins_needing_msa: list[tuple[int, BoltzEntity]] = []
    for idx, mol in enumerate(molecules):
        if mol.type == BoltzEntityType.PROTEIN and mol.alignment is None:
            proteins_needing_msa.append((idx, mol))

    if not proteins_needing_msa:
        print("[Boltz MSA] No protein entities need automatic MSA generation")
        return

    print(
        f"[Boltz MSA] Generating MSA for {len(proteins_needing_msa)} protein(s) "
        f"using MSA Search NIM ({msa_mode})"
    )

    try:
        msa_service = _get_msa_search_service(msa_mode, app_username)

        if len(proteins_needing_msa) == 1:
            # Single protein: use encode()
            _generate_msa_single(proteins_needing_msa, msa_service)
        elif len(proteins_needing_msa) <= 8:
            # 2-8 proteins: use encode_paired() for better paired alignments
            _generate_msa_paired(proteins_needing_msa, msa_service)
        else:
            # >8 proteins: encode_paired() supports max 8 chains, fall back
            # to individual encode() calls for each protein
            print(
                f"[Boltz MSA] >8 protein chains ({len(proteins_needing_msa)}), "
                "using individual MSA search (paired MSA supports max 8 chains)"
            )
            for protein in proteins_needing_msa:
                try:
                    _generate_msa_single([protein], msa_service)
                except Exception as e:
                    _idx, entity = protein
                    print(
                        f"[Boltz MSA] WARNING: MSA failed for entity "
                        f"'{entity.id}': {e}. Continuing with remaining proteins."
                    )

    except Exception as e:
        # Graceful fallback: leave alignments as None
        # (Boltz will use empty MSA for these entities)
        print(
            f"[Boltz MSA] WARNING: MSA Search NIM failed ({e}). "
            "Falling back to empty MSA for affected protein entities."
        )


def _generate_msa_single(
    proteins: list[tuple[int, BoltzEntity]],
    msa_service,
) -> None:
    """Generate MSA for a single protein entity via encode()."""
    _idx, entity = proteins[0]
    print(f"[Boltz MSA] Running monomer MSA search for entity '{entity.id}'")

    from models.msa_search_nim.schema import MSASearchEncodeRequest

    request = MSASearchEncodeRequest(
        items=[{"sequence": entity.sequence}],
    )

    with modal.enable_output():
        response = msa_service.encode.remote(request)

    # Response is a Pydantic model or dict — normalize
    if hasattr(response, "model_dump"):
        response = response.model_dump()

    results = response.get("results", [])
    if not results:
        print("[Boltz MSA] WARNING: MSA search returned no results")
        return

    alignments = _extract_alignments_from_nim_result(results[0].get("alignments", {}))
    if alignments:
        entity.alignment = alignments
        print(
            f"[Boltz MSA] Populated MSA for entity '{entity.id}' "
            f"with databases: {[db.value for db in alignments]}"
        )
    else:
        print(f"[Boltz MSA] No usable alignments returned for entity '{entity.id}'")


def _generate_msa_paired(
    proteins: list[tuple[int, BoltzEntity]],
    msa_service,
) -> None:
    """Generate paired MSA for multiple protein entities via encode_paired()."""
    sequences = [entity.sequence for _idx, entity in proteins]
    entity_ids = [entity.id for _idx, entity in proteins]
    print(
        f"[Boltz MSA] Running paired MSA search for {len(proteins)} chains: {entity_ids}"
    )

    from models.msa_search_nim.schema import MSAPairedEncodeRequest

    request = MSAPairedEncodeRequest(
        items=[{"sequence": seq} for seq in sequences],
    )

    with modal.enable_output():
        response = msa_service.encode_paired.remote(request)

    # Response is a Pydantic model or dict — normalize
    if hasattr(response, "model_dump"):
        response = response.model_dump()

    results = response.get("results", [])
    if len(results) != len(proteins):
        print(
            f"[Boltz MSA] WARNING: Expected {len(proteins)} results from paired "
            f"MSA search, got {len(results)}. Skipping MSA population."
        )
        return

    for (_idx, entity), result in zip(proteins, results, strict=True):
        alignments = _extract_alignments_from_nim_result(result.get("alignments", {}))
        if alignments:
            entity.alignment = alignments
            print(
                f"[Boltz MSA] Populated paired MSA for entity '{entity.id}' "
                f"with databases: {[db.value for db in alignments]}"
            )
        else:
            print(f"[Boltz MSA] No usable alignments returned for entity '{entity.id}'")


@app.cls(
    image=image,
    secrets=[cloudflare_r2_secret, redis_url_secret],
    volumes={"/boltz2-mols-vol": boltz2_mols_vol},
    enable_memory_snapshot=True,
    experimental_options={"enable_gpu_snapshot": True},
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class BoltzModel(BillingMixinSnap):
    app_username: str = modal.parameter(default="default_user")
    model_version: str = model_version

    @modal.enter(snap=True)
    def load_model(self):
        """Load model components on CPU for memory snapshot."""
        print(f"📸 Loading Boltz {model_version} model on CPU for memory snapshot...")

        self.model_dir = get_model_dir(model_version)

        print(f"🔍 Boltz model directory: {self.model_dir}")

        # Setup mols directory symlink for Boltz2
        if model_version == BoltzModelVersion.BOLTZ2:
            self._setup_mols_directory()

        # Save snapshot timing for billing
        self.save_snapshot_uptime()
        print(f"✅ Boltz {model_version} model loaded on CPU, snapshot saved")

    @modal.enter(snap=False)
    def setup_gpu(self):
        """Transfer model to GPU after snapshot restore."""
        print(f"🚀 Setting up Boltz {model_version} model on GPU...")

        # Initialize GPU-specific components if needed
        device = get_torch_device()
        print(f"📍 Using device: {device}")

        # Note: Billing is automatically started by BillingMixinSnap's billing_enter method
        print(f"✅ Boltz {model_version} model ready on GPU")

    def _setup_mols_directory(self):
        """Setup the mols directory symlink for Boltz2."""
        import tarfile

        # Path to the R2-downloaded mols.tar
        mols_tar = self.model_dir / "mols.tar"
        # Path to the volume (mount point)
        mols_vol_path = Path("/boltz2-mols-vol")
        # Path where you want the mols dir to appear in your model_dir
        mols_symlink = self.model_dir / "mols"

        print("Setting up mols directory for Boltz2...")
        print(f"  mols.tar path: {mols_tar} (exists: {mols_tar.exists()})")
        print(f"  volume path: {mols_vol_path} (exists: {mols_vol_path.exists()})")

        # Ensure volume directory exists
        mols_vol_path.mkdir(parents=True, exist_ok=True)

        # Extract to the volume if not already extracted
        if mols_tar.exists() and not any(mols_vol_path.iterdir()):
            print(f"Extracting {mols_tar} to {mols_vol_path}")
            with tarfile.open(mols_tar, "r") as tar:
                tar.extractall(mols_vol_path)
            print(f"✅ Extracted mols.tar to {mols_vol_path}")
        elif not mols_tar.exists():
            print(f"⚠️ WARNING: mols.tar not found at {mols_tar}")
        else:
            print("ℹ️ Volume already contains files, skipping extraction")

        # Ensure model directory exists
        self.model_dir.mkdir(parents=True, exist_ok=True)

        # Remove existing mols dir/symlink if present
        if mols_symlink.exists() or mols_symlink.is_symlink():
            os.unlink(mols_symlink)

        # Check if the source directory exists before creating symlink
        mols_source = mols_vol_path / "mols"
        if not mols_source.exists():
            print(f"⚠️ WARNING: Source directory {mols_source} does not exist")
            # Try without the nested 'mols' directory
            if mols_vol_path.exists() and any(mols_vol_path.iterdir()):
                print(f"  Using volume root directly: {mols_vol_path}")
                os.symlink(mols_vol_path, mols_symlink)
            else:
                print("⚠️ ERROR: No valid mols directory found to symlink")
        else:
            os.symlink(mols_source, mols_symlink)

        print(
            f"Symlinked {mols_symlink} -> {mols_symlink.resolve() if mols_symlink.exists() else 'BROKEN'}"
        )

    @modal.method()
    @modal_endpoint(app_name=app_name, debug=True)
    def predict(self, payload: BoltzPredictRequestType) -> BoltzPredictResponse:
        """Run Boltz structure prediction."""
        # Clear subprocess diagnostics from any previous request so that
        # _process_results never inspects stale output.
        self._last_stdout = ""
        self._last_stderr = ""

        # Validate batch size
        if len(payload.items) != 1:
            raise UserError("Only batch size 1 is supported currently.")

        input_item = payload.items[0]

        # Track temporary files for cleanup
        temp_files = []

        try:
            # Create temporary directory for all files
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_dir = Path(tmp_dir)
                out_dir = tmp_dir / "output"
                out_dir.mkdir(parents=True, exist_ok=True)

                # Log input details
                self._log_input_details(input_item, payload.params)

                # Validate any SMILES strings with rdkit before handing off to
                # the subprocess.  This surfaces kekulization / parse errors as
                # a clear UserError rather than a cryptic FileNotFoundError
                # after the subprocess fails silently.
                self._validate_smiles_inputs(input_item)

                # Auto-generate MSA for protein entities without alignments
                if payload.params.msa_search is not None:
                    _generate_msa_for_entities(
                        input_item.molecules,
                        payload.params.msa_search,
                        self.app_username,
                    )

                # Construct YAML data from input using utils
                try:
                    yaml_data = construct_yaml_data(
                        input_item.molecules,
                        getattr(input_item, "constraints", None),
                        getattr(input_item, "templates", None),
                        getattr(payload.params, "affinity", None),
                        temp_files,
                    )
                    yaml_string = yaml.dump(yaml_data)
                except UserError:
                    raise
                except Exception as e:
                    raise UserError(
                        f"Failed to prepare input for Boltz prediction: {e}. "
                        "Check alignment files and molecule definitions."
                    ) from e

                print("[Boltz] Final YAML to be used for prediction:")
                print(yaml_string)

                # Write YAML to temporary file
                yaml_path = tmp_dir / "input.yaml"
                with open(yaml_path, "w") as f:
                    f.write(yaml_string)

                # Run Boltz prediction
                predictions_dir = self._run_boltz_prediction(
                    yaml_path, out_dir, payload.params
                )

                # Process and return results
                return self._process_results(predictions_dir, payload.params)

        finally:
            # Clean up temporary files
            self._cleanup_temp_files(temp_files)

    def _validate_smiles_inputs(self, input_item) -> None:
        """Validate SMILES strings with rdkit before running the subprocess.

        Raises ``UserError`` with a clear message so the caller never sees the
        confusing ``FileNotFoundError`` that arises when boltz fails silently
        due to a ``KekulizeException`` inside the prediction pipeline.
        """
        for mol in input_item.molecules:
            if not mol.smiles:
                continue
            try:
                validate_smiles_with_rdkit(mol.smiles)
            except ValueError as exc:
                raise UserError(
                    f"Invalid SMILES for molecule '{mol.id}': {exc}"
                ) from exc

    def _log_input_details(self, input_item, params):
        """Log input details for debugging."""
        print(f"[Boltz] Constructing YAML for {len(input_item.molecules)} molecule(s)")

        for idx, mol in enumerate(input_item.molecules):
            print(f"  Molecule {idx}: id={mol.id}, type={mol.type}")
            if mol.alignment:
                print(f"    Alignment sources: {list(mol.alignment.keys())}")
            if mol.sequence:
                print(f"    Sequence: {mol.sequence[:20]}... (len={len(mol.sequence)})")
            if mol.smiles:
                print(f"    SMILES: {mol.smiles}")
            if mol.ccd:
                print(f"    CCD: {mol.ccd}")

        if getattr(input_item, "constraints", None):
            print(f"[Boltz] Constraints: {input_item.constraints}")
        if getattr(params, "affinity", None):
            print(f"[Boltz] Affinity property: {params.affinity}")
        if getattr(params, "include", None):
            print(f"[Boltz] Include parameters: {params.include}")

    def _run_boltz_prediction(self, yaml_path: Path, out_dir: Path, params) -> Path:
        """Execute the Boltz prediction command."""
        # Verify model directory exists and contains expected files
        if not self.model_dir.exists():
            raise UserError(f"Model directory does not exist: {self.model_dir}")

        print(f"Model directory contents: {list(self.model_dir.glob('*'))[:10]}")

        cmd = self._build_boltz_command(yaml_path, out_dir, params)
        print(f"Running command: {' '.join(cmd)}")

        process = self._execute_boltz_process(cmd)
        self._stream_process_output(process)
        self._check_process_completion(process)

        return out_dir / "boltz_results_input" / "predictions" / "input"

    def _build_boltz_command(self, yaml_path: Path, out_dir: Path, params) -> list[str]:
        """Build the Boltz prediction command with all parameters."""
        # Base command with required parameters
        cmd = [
            "boltz",
            "predict",
            str(yaml_path),
            "--out_dir",
            str(out_dir),
            "--cache",
            str(self.model_dir),
            "--recycling_steps",
            str(params.recycling_steps),
            "--sampling_steps",
            str(params.sampling_steps),
            "--diffusion_samples",
            str(params.diffusion_samples),
            "--step_scale",
            str(params.step_scale),
            "--accelerator",
            "gpu",
            "--devices",
            "1",
            "--num_workers",
            "2",
            "--output_format",
            "mmcif",
            "--model",
            f"{self.model_version}",
            "--max_msa_seqs",
            str(params.max_msa_seqs),
            "--num_subsampled_msa",
            str(params.num_subsampled_msa),
            "--preprocessing-threads",
            str(multiprocessing.cpu_count()),
            "--no_kernels",  # Skip cuequivariance kernels (not installed)
        ]

        # Add affinity parameters only for Boltz2
        if self.model_version == BoltzModelVersion.BOLTZ2:
            cmd.extend(
                [
                    "--sampling_steps_affinity",
                    str(getattr(params, "sampling_steps_affinity", 200)),
                    "--diffusion_samples_affinity",
                    str(getattr(params, "diffusion_samples_affinity", 5)),
                ]
            )

        # Add optional parameters
        self._add_optional_parameters(cmd, params)
        return cmd

    def _add_optional_parameters(self, cmd: list[str], params) -> None:
        """Add optional parameters to the command."""
        print(f"[Boltz] Processing include parameters: {params.include}")
        if params.seed is not None:
            cmd.extend(["--seed", str(params.seed)])
        # Always write PAE so ipSAE/ipae interface metrics are computed for
        # multi-chain predictions. The full PAE matrix is NOT returned in the
        # response (too large); only the derived metrics are included.
        cmd.append("--write_full_pae")
        if BoltzIncludeParams.PAE in params.include:
            print("[Boltz] PAE explicitly requested via include params")
        if BoltzIncludeParams.PDE in params.include:
            cmd.append("--write_full_pde")
            print("[Boltz] Added --write_full_pde flag")
        if BoltzIncludeParams.EMBEDDINGS in params.include:
            cmd.append("--write_embeddings")
            print("[Boltz] Added --write_embeddings flag")
        if getattr(params, "affinity_mw_correction", False):
            cmd.append("--affinity_mw_correction")
        if params.subsample_msa:
            cmd.append("--subsample_msa")
        if params.potentials:
            cmd.append("--use_potentials")

    # Default subprocess timeout: 2 hours.
    _SUBPROCESS_TIMEOUT_SEC = 7200

    def _execute_boltz_process(self, cmd: list[str]) -> subprocess.Popen:
        """Execute the Boltz command and return the process."""
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

    def _stream_process_output(self, process: subprocess.Popen) -> None:  # noqa: C901
        """Stream stdout in real-time, drain stderr in background, enforce timeout.

        Uses background threads to read both stdout and stderr concurrently,
        preventing pipe-buffer deadlocks when the subprocess writes heavily
        to stderr while we only drain stdout.

        Captured output is stored in ``self._last_stdout`` and
        ``self._last_stderr`` for downstream diagnostics.
        """
        # Cap retained stdout to avoid unbounded memory growth on verbose
        # runs (up to 2 hours).  Only the tail is needed for diagnostics.
        stdout_lines: collections.deque[str] = collections.deque(maxlen=500)
        stderr_chunks: list[str] = []

        def _read_stdout() -> None:
            try:
                for line in process.stdout:
                    stripped = line.rstrip("\n")
                    print(stripped)
                    stdout_lines.append(stripped)
            except (OSError, ValueError):
                # Pipe closed or I/O on closed file — expected during kill.
                pass

        def _drain_stderr() -> None:
            try:
                for line in process.stderr:
                    stderr_chunks.append(line)
            except (OSError, ValueError):
                pass

        stdout_thread = threading.Thread(target=_read_stdout, daemon=True)
        stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
        stdout_thread.start()
        stderr_thread.start()

        # Wait for the process to exit, enforcing a hard timeout.
        timeout = self._SUBPROCESS_TIMEOUT_SEC
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as e:
            process.kill()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                print("[Boltz] Warning: process did not exit after kill")
            stdout_thread.join(timeout=5)
            stderr_thread.join(timeout=5)
            self._last_stdout = "\n".join(stdout_lines)
            self._last_stderr = "".join(stderr_chunks)
            raise UserError(
                f"Boltz prediction timed out after {timeout // 60} minutes. "
                "This may indicate a hung MSA search, very long sequence, "
                "or too many diffusion_samples."
            ) from e

        # Process exited — wait for reader threads to finish draining.
        stdout_thread.join(timeout=10)
        stderr_thread.join(timeout=10)
        if stdout_thread.is_alive():
            print("[Boltz] Warning: stdout reader thread did not finish draining")
        if stderr_thread.is_alive():
            print("[Boltz] Warning: stderr reader thread did not finish draining")

        self._last_stdout = "\n".join(stdout_lines)
        self._last_stderr = "".join(stderr_chunks)

    def _check_process_completion(self, process: subprocess.Popen) -> None:
        """Check process completion and handle errors.

        Uses ``self._last_stderr`` captured by ``_stream_process_output``
        and interprets UNIX signals for actionable error messages.
        """
        stderr = getattr(self, "_last_stderr", "") or ""
        stdout = getattr(self, "_last_stdout", "") or ""
        if stderr:
            print(f"Boltz CLI stderr output:\n{stderr[:10000]}")

        if process.returncode == 0:
            return

        # Interpret signal-based kills (negative return codes).
        if process.returncode < 0:
            signal_num = -process.returncode
            if signal_num == 9:
                msg = (
                    "Boltz was killed by the system (SIGKILL), likely due to "
                    "GPU out of memory or container memory limit exceeded. "
                    "Try reducing sequence length, diffusion_samples, or "
                    "sampling_steps."
                )
            elif signal_num == 11:
                msg = (
                    "Boltz crashed with a segmentation fault (SIGSEGV). "
                    "This often indicates GPU memory corruption or an input "
                    "that triggers a known Boltz bug. Check sequence validity."
                )
            elif signal_num == 15:
                msg = "Boltz was terminated (SIGTERM)."
            else:
                msg = f"Boltz was killed by signal {signal_num}."
        else:
            msg = f"Boltz prediction failed with exit code {process.returncode}."

        if stderr:
            # Show head + tail of stderr (CUDA errors dump huge kernel source
            # at the start; the actual diagnostic is often at the end)
            msg += f"\n\nBoltz stderr ({len(stderr)} chars):\n{stderr[:5000]}"
            if len(stderr) > 10000:
                msg += f"\n\n[... {len(stderr) - 10000} chars truncated ...]\n\nBoltz stderr (tail):\n{stderr[-5000:]}"
        # Click sends tracebacks to stdout, so include the tail of stdout too.
        if stdout:
            # Show last 5000 chars of stdout which often contains the traceback.
            stdout_tail = stdout[-5000:] if len(stdout) > 5000 else stdout
            msg += f"\n\nBoltz stdout (tail):\n{stdout_tail}"

        raise UserError(msg)

    def _process_results(  # noqa: C901
        self, predictions_dir: Path, params
    ) -> BoltzPredictResponse:
        """Process prediction results and return response."""
        # Currently active result paths
        active_paths = {
            "mmcif": predictions_dir / "input_model_0.cif",
            "confidence": predictions_dir / "confidence_input_model_0.json",
            "affinity": predictions_dir / "affinity_input.json",
            "embeddings": predictions_dir / "embeddings_input.npz",
        }

        # Reserved paths (unused until re-enabled; disabled due to response size)
        _reserved_paths = {  # noqa: F841  # Keeping for future use
            "pae": predictions_dir / "pae_input_model_0.npz",
            "pde": predictions_dir / "pde_input_model_0.npz",
            "plddt": predictions_dir / "plddt_input_model_0.npz",
        }

        # Guard against a missing output file.  This can happen when the boltz
        # subprocess fails silently and exits with code 0 but writes no output
        # (upstream issue: github.com/jwohlwend/boltz/issues/167).
        if not active_paths["mmcif"].exists():
            hint = ""
            stdout = getattr(self, "_last_stdout", "") or ""
            stdout_lower = stdout.lower()
            if "ran out of memory" in stdout_lower:
                hint = (
                    " The GPU ran out of memory. Try reducing sequence "
                    "length, diffusion_samples, or sampling_steps."
                )
            elif "featurizer" in stdout_lower and "fail" in stdout_lower:
                hint = (
                    " The input failed during featurization. Check for "
                    "invalid residues or unsupported molecule types."
                )
            elif "Number of failed examples:" in stdout:
                hint = " Boltz reported failed predictions in its output."

            raise UserError(
                f"Boltz prediction did not produce an output structure.{hint} "
                "The subprocess exited successfully but wrote no output files."
            )

        # Read mmCIF structure
        with open(active_paths["mmcif"]) as f:
            mmcif_str = f.read()

        # Read confidence scores
        if not active_paths["confidence"].exists():
            raise UserError(
                "Boltz prediction did not produce confidence scores. "
                "The subprocess may have encountered an internal error "
                "(e.g., GPU out of memory). Check inputs and try again."
            )
        try:
            with open(active_paths["confidence"]) as f:
                confidence_data = json.load(f)
        except json.JSONDecodeError as e:
            raise UserError(
                f"Confidence scores file is corrupted: {e}. "
                "This may indicate a Boltz internal error."
            ) from e

        # Calculate ipSAE and ipae if PAE data is available
        # NOTE: We load the PAE matrix to calculate ipSAE/ipae metrics,
        # but we do NOT return the full PAE matrix in the response (too large).
        # Only the derived metrics (ipSAE, ipae) are returned in confidence scores.
        pair_chains_ipae = None
        pair_chains_ipsae = None
        if _reserved_paths["pae"].exists():
            try:
                pae_data = np.load(_reserved_paths["pae"])
                pae_matrix = pae_data["pae"]

                chain_ids, _coordinates, residue_types = parse_structure_from_cif(
                    mmcif_str
                )

                if chain_ids and len(chain_ids) == pae_matrix.shape[0]:
                    pair_chains_ipsae = calculate_ipsae(
                        pae_matrix,
                        chain_ids,
                        residue_types,
                        pae_cutoff=10.0,
                    )
                    print(
                        f"[Boltz] Calculated ipSAE for {len(pair_chains_ipsae)} chains"
                    )

                    pair_chains_ipae = calculate_ipae(pae_matrix, chain_ids)
                    print(f"[Boltz] Calculated ipae for {len(pair_chains_ipae)} chains")
                else:
                    print(
                        f"[Boltz] Warning: Structure dimensions don't match PAE matrix. "
                        f"Chain IDs: {len(chain_ids) if chain_ids else 0}, "
                        f"PAE matrix: {pae_matrix.shape[0]}"
                    )
            except Exception as e:
                print(f"[Boltz] Warning: Failed to calculate ipSAE/ipae: {e}")

        # Add ipae and ipSAE to confidence data if calculated
        if pair_chains_ipae is not None:
            confidence_data["pair_chains_ipae"] = pair_chains_ipae
        if pair_chains_ipsae is not None:
            confidence_data["pair_chains_ipsae"] = pair_chains_ipsae

        try:
            confidence = BoltzConfidenceScores(**confidence_data)
        except Exception as e:
            raise UserError(
                f"Failed to parse confidence scores: {e}. "
                "Boltz may have produced an unexpected output format."
            ) from e

        # Read affinity scores if available
        affinity = None
        affinity_requested = getattr(params, "affinity", None) is not None
        if active_paths["affinity"].exists():
            try:
                with open(active_paths["affinity"]) as f:
                    affinity_data = json.load(f)
                affinity = BoltzAffinityScores(**affinity_data)
            except json.JSONDecodeError as e:
                raise UserError(
                    f"Affinity scores file is corrupted: {e}. "
                    "This may indicate a Boltz internal error."
                ) from e
            except Exception as e:
                raise UserError(f"Failed to parse affinity scores: {e}.") from e
        elif affinity_requested:
            raise UserError(
                "Affinity scores were requested but not produced. "
                "The structure prediction may have failed silently "
                "(e.g., GPU out of memory). Try reducing sequence length "
                "or diffusion_samples."
            )

        # Read optional arrays if requested
        pae = None
        pde = None
        plddt = None
        embeddings = None

        # DISABLED: PAE/PDE/PLDDT arrays are too large to return in response
        # Instead, we calculate derived metrics (ipSAE, ipae) from PAE and return those
        # in the confidence scores (see above). This provides the key interface quality
        # metrics without the overhead of returning full N×N matrices.
        #
        # if BoltzIncludeParams.PAE in params.include and _reserved_paths["pae"].exists():
        #     pae = np.load(_reserved_paths["pae"])["pae"].tolist()
        #
        # if BoltzIncludeParams.PDE in params.include and _reserved_paths["pde"].exists():
        #     pde = np.load(_reserved_paths["pde"])["pde"].tolist()
        #
        # if BoltzIncludeParams.PLDDT in params.include and _reserved_paths["plddt"].exists():
        #     plddt = np.load(_reserved_paths["plddt"])["plddt"].tolist()

        if BoltzIncludeParams.EMBEDDINGS in params.include:
            embeddings_path = active_paths["embeddings"]
            print(f"[Boltz] Checking for embeddings file: {embeddings_path}")
            if embeddings_path.exists():
                try:
                    embeddings_data = np.load(embeddings_path)
                    print(
                        f"[Boltz] Embeddings data keys: "
                        f"{list(embeddings_data.keys())}"
                    )

                    s_data = embeddings_data["s"]
                    z_data = embeddings_data["z"]

                    print(
                        f"[Boltz] Original s shape: {s_data.shape}, "
                        f"dtype: {s_data.dtype}"
                    )
                    print(
                        f"[Boltz] Original z shape: {z_data.shape}, "
                        f"dtype: {z_data.dtype}"
                    )

                    # Remove batch dimension
                    s_data = s_data[0]
                    z_data = z_data[0]

                    s_list = s_data.tolist()
                    z_list = z_data.tolist()

                    embeddings = BoltzEmbeddings(s=s_list, z=z_list)
                    print(
                        f"[Boltz] Created embeddings: "
                        f"s={len(embeddings.s)}, z={len(embeddings.z)}"
                    )
                except (KeyError, ValueError, IndexError) as e:
                    raise UserError(
                        f"Failed to read embeddings file: {e}. "
                        "The file may be corrupted or have an "
                        "unexpected format."
                    ) from e
            else:
                print(
                    "[Boltz] Warning: embeddings were requested but "
                    "the file was not produced. The prediction may have "
                    "failed to write embeddings (e.g., OOM)."
                )
                embeddings = None

        return BoltzPredictResponse(
            results=[
                BoltzPredictResponseOutput(
                    cif=mmcif_str,
                    plddt=plddt,
                    pae=pae,
                    pde=pde,
                    embeddings=embeddings,
                    confidence=confidence,
                    affinity=affinity,
                )
            ]
        )

    def _cleanup_temp_files(self, temp_files: list):
        """Clean up temporary files."""
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    print(f"[Boltz] Cleaned up temp file: {temp_file}")
            except Exception as e:
                print(f"[Boltz] Warning: Failed to clean up temp file {temp_file}: {e}")


if __name__ == "__main__":
    """
    Usage:
        MODEL_VERSION="boltz2" python models/boltz/app.py
        MODEL_VERSION="boltz1" python models/boltz/app.py

        # Force deploy in QA/prod:
        MODEL_VERSION="boltz2" python models/boltz/app.py --force-deploy
    """
    run_or_deploy_modal_app(
        app,
        BoltzModel,
        description=f"Run and optionally deploy the {BoltzModelParams.display_name} {model_version} Modal app.",
    )
