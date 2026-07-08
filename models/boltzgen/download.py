from pathlib import Path
from typing import Any, Optional

from models.boltzgen.schema import BoltzGenParams
from models.commons.core.logging import get_logger
from models.commons.storage.acquisition import (
    AcquisitionConfig,
    AcquisitionStrategy,
    CacheConfig,
    HfSourceConfig,
    R2OnlyConfig,
    ValidationConfig,
)
from models.commons.storage.download_helpers import download_with_fallback
from models.commons.storage.downloads import get_model_dir_util

logger = get_logger(__name__)

### BoltzGen Model Artifacts Configuration

# HuggingFace repository and artifact paths
HF_REPO_ID = "boltzgen/boltzgen-1"
HF_REPO_ID_DATA = "boltzgen/inference-data"

# Pinned HuggingFace snapshot revisions (verified during container build 2026-02-17)
HF_MODEL_REVISION = "c1be29e1f82ffcc72264f64b993c43fb4e0d17f0"  # boltzgen/boltzgen-1
HF_DATA_REVISION = "c3d36fd276e9caf098c75d4113c6d5eb320b1a4c"  # boltzgen/inference-data

ARTIFACTS = {
    "design-diverse": {
        "repo_id": HF_REPO_ID,
        "filename": "boltzgen1_diverse.ckpt",
        "description": "BoltzGen design checkpoint (diverse variant)",
        "revision": HF_MODEL_REVISION,
    },
    "design-adherence": {
        "repo_id": HF_REPO_ID,
        "filename": "boltzgen1_adherence.ckpt",
        "description": "BoltzGen design checkpoint (adherence variant)",
        "revision": HF_MODEL_REVISION,
    },
    "inverse-fold": {
        "repo_id": HF_REPO_ID,
        "filename": "boltzgen1_ifold.ckpt",
        "description": "BoltzGen inverse folding checkpoint",
        "revision": HF_MODEL_REVISION,
    },
    "folding": {
        "repo_id": HF_REPO_ID,
        "filename": "boltz2_conf_final.ckpt",
        "description": "BoltzGen folding checkpoint",
        "revision": HF_MODEL_REVISION,
    },
    "affinity": {
        "repo_id": HF_REPO_ID,
        "filename": "boltz2_aff.ckpt",
        "description": "BoltzGen affinity prediction checkpoint",
        "revision": HF_MODEL_REVISION,
    },
    "moldir": {
        "repo_id": HF_REPO_ID_DATA,
        "filename": "mols.zip",
        "description": "Small molecule dictionary for BoltzGen",
        "repo_type": "dataset",
        "revision": HF_DATA_REVISION,
    },
}


def get_model_dir(sub_path: Optional[str] = None) -> Path:
    """Get the directory path for BoltzGen model weights."""
    return get_model_dir_util(
        base_model_slug=BoltzGenParams.base_model_slug,
        weights_version=BoltzGenParams.weights_version,
        model_variant=None,
        sub_path=sub_path,
    )


def _download_artifact(
    artifact_name: str,
    base_model_slug: str,
    weights_version: str,
    sub_path: Optional[str] = None,
) -> Path:
    """Download a single artifact using R2 cache with HuggingFace fallback."""
    artifact_config = ARTIFACTS[artifact_name]
    target_dir = get_model_dir(sub_path=sub_path or artifact_name)

    # Build expected file path
    expected_file = artifact_config["filename"]

    # Primary strategy: R2 cache
    primary_config = AcquisitionConfig(
        strategy=AcquisitionStrategy.R2_ONLY,
        target_dir=target_dir,
        cache_config=CacheConfig(enable_r2_cache=False),  # Reading from R2
        validation_config=ValidationConfig(
            required_files=[expected_file],
        ),
        r2_config=R2OnlyConfig(
            base_model_slug=base_model_slug,
            weights_version=weights_version,
            model_variant=None,
            sub_path=sub_path or artifact_name,
        ),
    )

    # Fallback strategy: Download from HuggingFace
    fallback_config = AcquisitionConfig(
        strategy=AcquisitionStrategy.HUGGINGFACE_HUB,
        target_dir=target_dir,
        cache_config=CacheConfig(enable_r2_cache=True),  # Cache back to R2
        validation_config=ValidationConfig(
            required_files=[expected_file],
        ),
        hf_config=HfSourceConfig(
            repo_id=artifact_config["repo_id"],
            revision=artifact_config.get(
                "revision", "main"
            ),  # Default to "main" if not specified
            allow_patterns=[artifact_config["filename"]],
            repo_type=artifact_config.get("repo_type", "model"),
        ),
    )

    result = download_with_fallback(primary_config, fallback_config)

    if not result.success:
        raise RuntimeError(
            f"Failed to download {artifact_name}: {result.error_message}"
        )

    logger.info("Downloaded %s (%s)", artifact_name, artifact_config["description"])
    return result.actual_model_path or target_dir


def download_model_assets(
    base_model_slug: str,
    weights_version: str,
    variant_config: Optional[dict[str, Any]] = None,
    sub_path: Optional[str] = None,
) -> Path:
    """Download all BoltzGen model assets.

    Downloads all required checkpoints and data files:
    - Design checkpoints (diverse and adherence)
    - Inverse folding checkpoint
    - Folding checkpoint
    - Affinity prediction checkpoint
    - Small molecule dictionary (mols.zip)

    Args:
        base_model_slug: The base model identifier (e.g., "boltzgen")
        weights_version: Version of the model parameters (e.g., "v1")
        variant_config: Optional variant configuration (not used for boltzgen)
        sub_path: Optional subdirectory path

    Returns:
        Path to the downloaded model directory

    Note:
        The mols.zip file is downloaded but NOT extracted here.
        Extraction is handled by app.py during container setup.
    """
    logger.info("Downloading BoltzGen model assets...")

    for artifact_name in ARTIFACTS:
        _download_artifact(artifact_name, base_model_slug, weights_version, sub_path)

    logger.info("All BoltzGen model assets downloaded successfully")
    return get_model_dir()
