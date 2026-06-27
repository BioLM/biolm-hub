import math
import os
import random
import tempfile
from statistics import mode

import modal

from models.commons.model.base import ModelMixinSnap
from models.commons.core.decorator import modal_endpoint
from models.commons.core.error import UserError
from models.commons.modal.downloader import setup_download_layer
from models.commons.modal.source import setup_source_layer
from models.commons.model.config import biolm_model_class
from models.commons.util.config import (
    cloudflare_r2_secret,
    common_requirements,
)
from models.propermab.config import MODEL_FAMILY
from models.propermab.download import get_model_dir
from models.propermab.schema import (
    ProperMABExtractFeaturesMetadata,
    ProperMABExtractFeaturesParams,
    ProperMABExtractFeaturesRequest,
    ProperMABExtractFeaturesResponse,
    ProperMABExtractFeaturesResponseResult,
    ProperMABParams,
    ProperMABSequenceFeatures,
    ProperMABStructureFeatures,
)


def prebuild_amber_siz() -> None:
    """Pre-download amber.siz atomic radii file during image build.

    This function downloads amber.siz using the R2-first download infrastructure,
    then creates a symlink at /opt/amber.siz for APBS/NanoShaper to use.

    The amber.siz file contains AMBER98 force field van der Waals radii,
    used by NanoShaper for molecular surface calculations.

    Scientific References:
    - AMBER98 force field van der Waals radii (derived from TINKER package)
    - DelPhi/NanoShaper .siz format specification

    Sources (in order of preference):
    1. R2 cache: r2://biolm-modal/model-store/propermab/v1/amber.siz
    2. Clemson: http://compbio.clemson.edu/downloadDir/delphi/parameters.tar.gz
    """
    import sys

    # Add the root to path for imports
    sys.path.insert(0, "/root")

    from models.propermab.download import download_amber_siz

    print("🔧 Pre-downloading amber.siz during image build...")

    # Download using the proper R2-first infrastructure
    cached_path = download_amber_siz()

    # Create symlink at /opt/amber.siz for APBS/NanoShaper
    import os

    target_path = "/opt/amber.siz"
    if os.path.exists(target_path):
        os.remove(target_path)
    os.symlink(str(cached_path), target_path)
    print(f"✅ Created symlink: {target_path} -> {cached_path}")


def install_apbs_dependencies() -> None:
    """Install APBS v3.0.0 and its dependencies during image build.

    APBS (Adaptive Poisson-Boltzmann Solver) is required for electrostatic
    potential calculations. Version 3.0.0 is specifically required as later
    versions have API incompatibilities.

    This function:
    1. Downloads APBS 3.0.0 binary distribution
    2. Extracts to /opt/APBS-3.0.0.Linux/
    3. Installs readline 7.0 (APBS dependency)

    Note: amber.siz is downloaded separately via prebuild_amber_siz() using
    the R2-first download infrastructure.
    """
    import subprocess
    import tarfile

    print("🔧 Installing APBS 3.0.0 and dependencies...")

    # Create installation directories
    os.makedirs("/opt", exist_ok=True)
    os.makedirs("/tmp/apbs_install", exist_ok=True)

    try:
        # Download APBS 3.0.0
        print("📥 Downloading APBS 3.0.0...")
        subprocess.run(
            [
                "wget",
                "-q",
                "https://github.com/Electrostatics/apbs/releases/download/v3.0.0/APBS-3.0.0_Linux.zip",
                "-O",
                "/tmp/apbs_install/APBS-3.0.0_Linux.zip",
            ],
            check=True,
        )

        # Extract APBS
        print("📦 Extracting APBS...")
        subprocess.run(
            [
                "unzip",
                "-q",
                "/tmp/apbs_install/APBS-3.0.0_Linux.zip",
                "-d",
                "/tmp/apbs_install",
            ],
            check=True,
        )
        subprocess.run(
            ["mv", "/tmp/apbs_install/APBS-3.0.0.Linux", "/opt/"],
            check=True,
        )

        # Install readline 7.0 (APBS dependency)
        print("📥 Installing readline 7.0...")
        subprocess.run(
            [
                "wget",
                "-q",
                "http://ftp.gnu.org/gnu/readline/readline-7.0.tar.gz",
                "-O",
                "/tmp/apbs_install/readline-7.0.tar.gz",
            ],
            check=True,
        )

        # Extract readline
        with tarfile.open("/tmp/apbs_install/readline-7.0.tar.gz", "r:gz") as tar:
            tar.extractall("/tmp/apbs_install/")

        # Compile and install readline
        print("🔨 Compiling readline 7.0...")
        os.chdir("/tmp/apbs_install/readline-7.0")
        subprocess.run(
            ["./configure", "--prefix=/opt/readline"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            ["make", "-j4"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            ["make", "install"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Verify installations
        print("✅ Verifying APBS installation...")
        apbs_version = subprocess.run(
            ["/opt/APBS-3.0.0.Linux/bin/apbs", "--version"],
            capture_output=True,
            text=True,
        )
        print(f"   APBS version: {apbs_version.stdout.strip()}")

        print("✅ APBS and dependencies installed successfully!")

    except Exception as e:
        print(f"⚠️ Error installing APBS: {e}")
        print("   ProperMAB will attempt to continue but may fail at runtime")

    finally:
        # Clean up installation files
        if os.path.exists("/tmp/apbs_install"):
            subprocess.run(["rm", "-rf", "/tmp/apbs_install"], check=False)


def prebuild_abodybuilder2() -> None:
    """Pre-verify ABodyBuilder2 weights exist during build phase.

    This function verifies that the ABodyBuilder2 model weights are present
    after R2 download. We avoid importing torch/ImmuneBuilder during image
    build to prevent numpy/numba CPU dispatcher conflicts.

    The actual model loading happens at runtime in configure_model().
    """
    model_dir = get_model_dir()

    print("🔄 Pre-verifying ABodyBuilder2 weights during build phase...")
    print(f"📂 Model directory: {model_dir}")

    # Expected weight files for ABodyBuilder2
    expected_weights = [
        "antibody_model_1",
        "antibody_model_2",
        "antibody_model_3",
        "antibody_model_4",
    ]

    # Check if weights exist
    if model_dir.exists():
        existing_files = list(model_dir.iterdir())
        existing_names = [f.name for f in existing_files]
        print(f"📋 Found {len(existing_files)} files in model directory")

        missing = [w for w in expected_weights if w not in existing_names]
        if missing:
            print(f"⚠️ Missing weight files: {missing}")
            print("💡 Weights will be downloaded at runtime from Zenodo")
        else:
            print("✅ All ABodyBuilder2 weight files present!")
            for w in expected_weights:
                weight_path = model_dir / w
                if weight_path.exists():
                    size_mb = weight_path.stat().st_size / (1024 * 1024)
                    print(f"   ✓ {w}: {size_mb:.1f} MB")
    else:
        print("⚠️ Model directory does not exist")
        print("💡 Weights will be downloaded at runtime from Zenodo")


# Build Modal container image with all ProperMAB dependencies
# This is a complex setup requiring:
# - APBS 3.0.0 for electrostatics
# - NanoShaper for surface mesh generation
# - OpenMM for molecular dynamics
# - ImmuneBuilder for structure prediction
# - FreeSASA for solvent accessibility
# - HMMER/ANARCI for antibody numbering
image = modal.Image.micromamba(python_version="3.11")

# Setup download layer with ABodyBuilder2 weights (R2-first strategy)
image = setup_download_layer(
    image,
    base_model_slug=ProperMABParams.base_model_slug,
    params_version=ProperMABParams.params_version,
    variant_config={},  # No variants for ProperMAB
)

# Add all dependencies
image = (
    image.apt_install("procps")  # Critical for computing container uptime
    .apt_install(
        # Build tools
        "wget",
        "unzip",
        "build-essential",
        "git",
        # System libraries
        "libopenblas-dev",
        # APBS dependencies - needs ncurses/tinfo for libtinfo.so.5
        "libtinfo5",
        "libncurses5",
    )
    .uv_pip_install(common_requirements)
    # Install conda packages (OpenMM, pdbfixer, hmmer) using micromamba
    # Also install libstdcxx (the actual C++ library) to provide GLIBCXX_3.4.29
    # which OpenMM requires but the Debian base image's system libstdc++ lacks.
    .micromamba_install("openmm", "pdbfixer", "libstdcxx", channels=["conda-forge"])
    .micromamba_install("hmmer=3.3.2", channels=["conda-forge", "bioconda"])
    # Install ANARCI for antibody numbering (PyPI package includes pre-built
    # germline data — avoids flaky IMGT server fetches during source build)
    .uv_pip_install("anarci==2026.2.13.2")
    # Install Python dependencies with exact versions for reproducibility
    # NOTE: numpy and biopython installed via pip to avoid conda libstdc++ conflicts
    .uv_pip_install(
        "numpy==1.24.4",  # Pin numpy for scipy/numba compatibility
        "biopython==1.79",  # PDB parsing - installed via pip to find numpy
        "scipy==1.10.1",  # Numerical computations
        "numba==0.60.0",  # JIT compilation (0.60 adds numpy 2.0 support)
        "ImmuneBuilder==1.2",  # ABodyBuilder2 - matches immunebuilder model
        "freesasa==2.2.1",  # SASA calculations (2.2.1 adds Python 3.11 support)
        "open3d==0.18.0",  # 3D geometry processing (0.18 added Python 3.11 support)
        "plyfile==1.0.0",  # PLY mesh format
        "meshio==5.3.4",  # Mesh I/O
        "pdb2pqr==3.6.1",  # PDB to PQR conversion
        # Additional propermab dependencies (since we use --no-deps)
        "py3Dmol==2.5.3",  # 3D molecular visualization
        "seaborn==0.13.2",  # Statistical plotting
        "fair-esm==2.0.0",  # ESM protein language models
        "antiberty==0.1.3",  # Antibody language model
    )
    # Install APBS and dependencies via custom function
    .run_function(install_apbs_dependencies)
    # Download amber.siz using R2-first strategy (requires secrets for R2 access)
    .run_function(prebuild_amber_siz, secrets=[cloudflare_r2_secret])
    # Set up environment variables for APBS and OpenMM
    # Note: Modal doesn't support variable expansion, so we set full paths
    # LD_PRELOAD forces loading conda's libstdc++ before OpenMM looks for it,
    # solving the GLIBCXX_3.4.29 not found error.
    .env(
        {
            "LD_LIBRARY_PATH": "/opt/readline/lib:/opt/APBS-3.0.0.Linux/lib:/opt/conda/lib",
            "LD_PRELOAD": "/opt/conda/lib/libstdc++.so.6",
            "PATH": "/opt/APBS-3.0.0.Linux/bin:/opt/conda/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "PYTHONPATH": "/tmp/propermab",
        }
    )
    # Fix numpy/scipy/numba/biopython conflicts: conda packages require specific numpy versions
    # - scipy conda: compiled against numpy <1.27 → needs pip scipy for numpy 2.x compat
    # - numba conda (0.60): requires numpy <2.1 → need numpy <2.0 OR pip numba
    # Solution: Pin numpy to 1.26.x and reinstall scipy, numba, biopython via pip
    # IMPORTANT: Pin all versions — unpinned scipy/numba resolve to incompatible versions
    .run_commands(
        "pip install --force-reinstall numpy==1.26.4 scipy==1.10.1 numba==0.60.0 biopython==1.79",
        # Verify imports work correctly
        "python -c 'import numpy; import scipy; import numba; from Bio.PDB import PDBParser; print(f\"✅ NumPy {numpy.__version__}, SciPy {scipy.__version__}, Numba {numba.__version__}, Biopython PDB verified\")'",
    )
    # Clone and install ProperMAB AFTER force-reinstall to avoid broken editable install
    # Use --no-deps to avoid dependency conflicts (we already installed all deps above)
    # Fix IPython import BEFORE install: propermab uses deprecated IPython.core.display
    .run_commands(
        "git clone https://github.com/regeneron-mpds/propermab.git /tmp/propermab",
        "sed -i 's/from IPython.core.display import display, HTML/from IPython.display import display, HTML/' /tmp/propermab/propermab/plot/protein.py",
        # No pip install needed: propermab's setup.py only lists packages=['propermab']
        # (missing subpackages like plot, structure, features, models), so non-editable
        # install is incomplete. PYTHONPATH=/tmp/propermab (set in .env() above) makes
        # all subpackages importable directly from the git clone.
    )
    # Pre-verify ABodyBuilder2 weights during build
    .run_function(prebuild_abodybuilder2)
)
# Finally, add all model files
image = setup_source_layer(MODEL_FAMILY.base_model_slug)(image)


# Define the app using unified config
app_name, modal_resource_spec = MODEL_FAMILY.get_app_config()
print(f"App name: {app_name}")
app = modal.App(app_name, image=image)


@app.cls(
    image=image,
    secrets=[cloudflare_r2_secret],
    enable_memory_snapshot=True,
    **modal_resource_spec.to_modal_options(),
)
@biolm_model_class
class ProperMABModel(ModelMixinSnap):
    """ProperMAB model for extracting 34 biophysical features from antibodies.

    ProperMAB is a feature engineering framework that extracts structure-aware
    molecular descriptors proven to predict antibody developability properties:
    - HIC retention time (r=0.71)
    - High-concentration viscosity (ρ=0.48)
    - Aggregation propensity
    - Solubility

    The model:
    1. Predicts 3D structure using ABodyBuilder2 (EGNN-based)
    2. Calculates 7 sequence features (instant)
    3. Calculates 27 structure features (~60s):
       - Charge distribution (6 features)
       - Hydrophobicity (6 features)
       - Charge patches (4 features)
       - Aromatic features (3 features)
       - Spatial statistics (6 features)
       - Domain asymmetry (2 features)

    Reference:
        Li et al. (2025). "PROPERMAB: structure-aware biophysical descriptors
        for prediction of antibody developability properties." mAbs 17, 2474521.
    """

    app_username: str = modal.parameter(default="default_user")

    @modal.enter(snap=True)
    def load_propermab(self) -> None:
        """Load ProperMAB modules and configure external binaries.

        This runs during memory snapshot creation (before billing starts).
        Configures ProperMAB with paths to R2-cached ABodyBuilder2 weights
        and external tools (APBS, NanoShaper, etc.).
        """
        import propermab
        from propermab import defaults

        print("🔧 Configuring ProperMAB...")

        # Get model directory with R2-cached ABodyBuilder2 weights
        model_dir = get_model_dir()
        print(f"📂 ABodyBuilder2 weights directory: {model_dir}")

        # Verify weights exist
        if model_dir.exists() and any(model_dir.iterdir()):
            print("🚀 Using R2-cached ABodyBuilder2 weights")
        else:
            print("⚠️ Warning: ABodyBuilder2 weights not found in cache")

        # ProperMAB configuration for external binaries
        propermab_config = {
            "hmmer_binary_path": "/opt/conda/bin",  # HMMER installed via micromamba
            "nanoshaper_binary_path": "/opt/APBS-3.0.0.Linux/bin/NanoShaper",
            "apbs_binary_path": "/opt/APBS-3.0.0.Linux/bin/apbs",
            "pdb2pqr_path": "pdb2pqr",
            "multivalue_binary_path": "/opt/APBS-3.0.0.Linux/share/apbs/tools/bin/multivalue",
            "atom_radii_file": "/opt/amber.siz",
            "immunebuilder_weights_dir": str(
                model_dir
            ),  # Use R2-cached weights instead of auto-download
            "apbs_ld_library_paths": ["/opt/readline/lib", "/opt/APBS-3.0.0.Linux/lib"],
        }

        # Configure ProperMAB with paths (use override_defaults, not update)
        defaults.system_config.override_defaults(propermab_config)

        # Verify configuration
        print("📋 ProperMAB configuration:")
        for key, value in propermab_config.items():
            print(f"   {key}: {value}")

        # Store propermab module for later use
        self.propermab = propermab

        print("✅ ProperMAB configured successfully!")

    @modal.enter(snap=False)
    def setup_model(self) -> None:
        """Complete model setup after snapshot restoration.

        This runs after memory snapshot is loaded (billing starts here).
        """
        print(
            f"✅ {ProperMABParams.display_name} model ready for inference from memory snapshot!"
        )

    def seed_everything(self, seed: int = 42, deterministic: bool = True) -> None:
        """Set seed for reproducibility across random, NumPy, and PyTorch.

        This ensures deterministic behavior for structure prediction and feature
        extraction, which is critical for reproducible results.

        Args:
            seed: Random seed value
            deterministic: If True, sets flags for deterministic behavior
        """
        import numpy as np
        import torch

        # Python & NumPy
        random.seed(seed)
        np.random.seed(seed)

        # PyTorch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed(seed)
            torch.cuda.manual_seed_all(seed)  # for multi-GPU

        # PyTorch determinism
        torch.backends.cudnn.deterministic = deterministic
        torch.backends.cudnn.benchmark = False

    @modal.method()
    @modal_endpoint(app_name=app_name)
    def extract_features(  # noqa: C901
        self, payload: ProperMABExtractFeaturesRequest
    ) -> ProperMABExtractFeaturesResponse:
        """Extract 34 biophysical features from antibody sequences.

        This endpoint:
        1. Validates input sequences
        2. Sets random seed for reproducibility
        3. Calculates sequence features (7 features) - instant
        4. Predicts 3D structure using ABodyBuilder2
        5. Calculates structure features (27 features) - ~60s per run
        6. Returns comprehensive feature dictionary

        Args:
            payload: Request containing heavy/light chain sequences and parameters

        Returns:
            Response containing 34 features separated into sequence (7) and structure (27)

        Raises:
            UserError: For invalid sequences or feature extraction failures
        """
        from propermab.features import feature_utils

        # Define expected features for validation
        EXPECTED_SEQ_FEATURES = {
            "theoretical_pi",
            "n_charged_res",
            "n_charged_res_fv",
            "fv_charge",
            "fv_csp",
            "fc_charge",
            "fab_fc_csp",
        }

        EXPECTED_STRUCT_FEATURES = {
            # Charge distribution (6)
            "net_charge",
            "exposed_net_charge",
            "net_charge_cdr",
            "exposed_net_charge_cdr",
            "scm",
            "dipole_moment",
            # Hydrophobicity (6)
            "hyd_asa",
            "hph_asa",
            "hyd_moment",
            "heiden_score",
            "hyd_patch_area",
            "hyd_patch_area_cdr",
            # Charge patches (4)
            "pos_patch_area",
            "pos_patch_area_cdr",
            "neg_patch_area",
            "neg_patch_area_cdr",
            # Aromatic (3)
            "aromatic_asa",
            "aromatic_cdr",
            "exposed_aromatic",
            # Spatial stats (6)
            "pos_ann_index",
            "neg_ann_index",
            "aromatic_ann_index",
            "pos_ripley_k",
            "neg_ripley_k",
            "aromatic_ripley_k",
            # Domain asymmetry (2)
            "Fv_chml",
            "exposed_Fv_chml",
            # CDR length (1)
            "cdr_h3_length",
        }

        # Integer features that should use mode instead of mean
        INTEGER_FEATURES = {"aromatic_cdr", "exposed_aromatic", "cdr_h3_length"}

        def validate_features(
            features_dict: dict, expected_features: set, feature_type: str
        ) -> None:
            """Validate that all expected features are present with valid values."""
            missing = expected_features - set(features_dict.keys())
            if missing:
                raise UserError(
                    f"Missing {feature_type} features: {missing}. "
                    f"ProperMAB library may have changed."
                ) from None

            # Validate values aren't None/NaN (handles both scalars and lists)
            for key, value in features_dict.items():
                if value is None:
                    raise UserError(
                        f"Invalid value for {feature_type} feature '{key}': None"
                    ) from None
                elif isinstance(value, float) and math.isnan(value):
                    raise UserError(
                        f"Invalid value for {feature_type} feature '{key}': NaN"
                    ) from None
                elif isinstance(value, list):
                    # Check each element in multi-run lists for NaN/None
                    for i, v in enumerate(value):
                        if v is None or (isinstance(v, float) and math.isnan(v)):
                            raise UserError(
                                f"Invalid value for {feature_type} feature '{key}' "
                                f"at run {i}: {v}"
                            ) from None

        results = []

        for item in payload.items:
            try:
                # Extract parameters
                params = payload.params or ProperMABExtractFeaturesParams()
                num_runs = params.num_runs
                is_fv = params.is_fv
                isotype = params.isotype.value
                lc_type = params.lc_type.value
                seed = params.seed

                # Set seed for reproducibility
                self.seed_everything(seed)

                # Validate sequences
                heavy_seq = item.heavy_seq.strip().upper()
                light_seq = item.light_seq.strip().upper()

                # Use temporary directory for intermediate files
                with tempfile.TemporaryDirectory() as tmp_dir:
                    print(
                        f"🔬 Extracting features: num_runs={num_runs}, is_fv={is_fv}, "
                        f"isotype={isotype}, lc_type={lc_type}, seed={seed}"
                    )

                    # STEP 1: Extract sequence-based features (7 features, instant)
                    print("📊 Computing sequence features (7 features)...")
                    seq_features_raw = feature_utils.get_all_seq_features(
                        heavy_seq=heavy_seq,
                        light_seq=light_seq,
                        is_fv=is_fv,
                        isotype=isotype,
                        lc_type=lc_type,
                        pH=7.4,
                    )

                    # Validate sequence features
                    validate_features(
                        seq_features_raw, EXPECTED_SEQ_FEATURES, "sequence"
                    )

                    # STEP 2: Extract structure-based features (27 features, ~60s per run)
                    print(
                        f"🧬 Computing structure features (27 features, {num_runs} run(s))..."
                    )
                    struct_features_raw = feature_utils.get_all_mol_features(
                        heavy_seq=heavy_seq,
                        light_seq=light_seq,
                        num_runs=num_runs,
                        tmp_dir=tmp_dir,
                    )

                    # Validate structure features
                    validate_features(
                        struct_features_raw, EXPECTED_STRUCT_FEATURES, "structure"
                    )

                    # STEP 3: Process features
                    # Sequence features are scalars - use directly
                    seq_features = dict(seq_features_raw)

                    # Structure features are lists when num_runs > 1 - average them appropriately
                    struct_features = {}
                    for key, value in struct_features_raw.items():
                        if isinstance(value, list):
                            # Check for empty list
                            if not value:
                                raise UserError(
                                    f"Feature '{key}' has no values - structure prediction failed"
                                ) from None

                            # Handle integer features specially
                            if key in INTEGER_FEATURES:
                                # For integers: use mode (most common) or round
                                try:
                                    struct_features[key] = mode(value)
                                except Exception:
                                    # If mode fails (no unique mode), use rounding
                                    struct_features[key] = round(
                                        sum(value) / len(value)
                                    )
                            else:
                                # For floats: average normally
                                struct_features[key] = sum(value) / len(value)
                        else:
                            struct_features[key] = value

                    # STEP 4: Build response models with validated integer conversion
                    # Sequence features (7)
                    try:
                        sequence_features = ProperMABSequenceFeatures(
                            theoretical_pi=seq_features["theoretical_pi"],
                            n_charged_res=int(seq_features["n_charged_res"]),
                            n_charged_res_fv=int(seq_features["n_charged_res_fv"]),
                            fv_charge=seq_features["fv_charge"],
                            fv_csp=seq_features["fv_csp"],
                            fc_charge=seq_features["fc_charge"],
                            fab_fc_csp=seq_features["fab_fc_csp"],
                        )
                    except (ValueError, TypeError) as e:
                        raise UserError(
                            f"Invalid sequence feature values: {str(e)}"
                        ) from e

                    # Structure features (27)
                    try:
                        structure_features = ProperMABStructureFeatures(
                            # Charge distribution (6)
                            net_charge=struct_features["net_charge"],
                            exposed_net_charge=struct_features["exposed_net_charge"],
                            net_charge_cdr=struct_features["net_charge_cdr"],
                            exposed_net_charge_cdr=struct_features[
                                "exposed_net_charge_cdr"
                            ],
                            scm=struct_features["scm"],
                            dipole_moment=struct_features["dipole_moment"],
                            # Hydrophobicity (6)
                            hyd_asa=struct_features["hyd_asa"],
                            hph_asa=struct_features["hph_asa"],
                            hyd_moment=struct_features["hyd_moment"],
                            heiden_score=struct_features["heiden_score"],
                            hyd_patch_area=struct_features["hyd_patch_area"],
                            hyd_patch_area_cdr=struct_features["hyd_patch_area_cdr"],
                            # Charge patches (4)
                            pos_patch_area=struct_features["pos_patch_area"],
                            pos_patch_area_cdr=struct_features["pos_patch_area_cdr"],
                            neg_patch_area=struct_features["neg_patch_area"],
                            neg_patch_area_cdr=struct_features["neg_patch_area_cdr"],
                            # Aromatic features (3)
                            aromatic_asa=struct_features["aromatic_asa"],
                            aromatic_cdr=int(struct_features["aromatic_cdr"]),
                            exposed_aromatic=int(struct_features["exposed_aromatic"]),
                            # Spatial statistics (6)
                            pos_ann_index=struct_features["pos_ann_index"],
                            neg_ann_index=struct_features["neg_ann_index"],
                            aromatic_ann_index=struct_features["aromatic_ann_index"],
                            pos_ripley_k=struct_features["pos_ripley_k"],
                            neg_ripley_k=struct_features["neg_ripley_k"],
                            aromatic_ripley_k=struct_features["aromatic_ripley_k"],
                            # Domain asymmetry (2)
                            Fv_chml=struct_features["Fv_chml"],
                            exposed_Fv_chml=struct_features["exposed_Fv_chml"],
                            # CDR length (1) - from structure
                            cdr_h3_length=int(struct_features["cdr_h3_length"]),
                        )
                    except (ValueError, TypeError) as e:
                        raise UserError(
                            f"Invalid structure feature values: {str(e)}"
                        ) from e

                    # Create metadata
                    metadata = ProperMABExtractFeaturesMetadata(
                        num_runs=num_runs,
                        isotype=isotype,
                        lc_type=lc_type,
                    )

                    # Create result
                    result = ProperMABExtractFeaturesResponseResult(
                        sequence_features=sequence_features,
                        structure_features=structure_features,
                        metadata=metadata,
                    )
                    results.append(result)

                    print(
                        "✅ Successfully extracted 34 features (7 sequence + 27 structure)"
                    )

            except ValueError as e:
                # User input errors
                raise UserError(f"Invalid input: {str(e)}") from e
            except KeyError as e:
                # Missing feature in ProperMAB output
                raise UserError(
                    f"Missing feature in ProperMAB output: {str(e)}. "
                    f"This may indicate a library version mismatch."
                ) from e
            except RuntimeError as e:
                # Runtime errors (e.g., APBS failures)
                error_msg = str(e)
                if "APBS" in error_msg or "electrostatic" in error_msg.lower():
                    raise UserError(
                        f"Electrostatics calculation failed: {error_msg}. "
                        f"This may indicate issues with antibody structure."
                    ) from e
                raise UserError(f"Feature extraction failed: {error_msg}") from e
            except UserError:
                # Let UserErrors pass through with their actionable messages
                raise
            except Exception as e:
                # Internal errors
                import traceback

                error_trace = traceback.format_exc()
                print(f"❌ Error extracting features: {error_trace}")
                raise UserError(
                    f"Unexpected error during feature extraction: {str(e)}"
                ) from e

        return ProperMABExtractFeaturesResponse(results=results)


if __name__ == "__main__":
    """Run or deploy the ProperMAB Modal app.

    Usage:
        python models/propermab/app.py

        # Force deploy to QA or main:
        python models/propermab/app.py --force-deploy
    """
    from models.commons.modal.deployment import run_or_deploy_modal_app

    run_or_deploy_modal_app(
        app,
        ProperMABModel,
        description=f"Run and optionally deploy the {ProperMABParams.display_name} Modal app.",
    )
