"""Download module for AbodyBuilder3 weights.

R2 cache first; on a miss fetch from the two upstream sources and cache the
combined, flat layout back to R2 so ``git clone -> deploy`` self-populates:

  - Structure-module checkpoints from the authors' Zenodo record (open /
    CC-BY-4.0), packaged in ``output.tar.gz`` as ``<model>-loss/best_second_stage.ckpt``.
    The loader reads ``<model_dir>/{plddt,language}-loss/best_second_stage.ckpt``.
  - The ProtT5 language model (``Rostlab/prot_t5_xl_uniref50``) used by the
    LANGUAGE variant, loaded flat via ``from_pretrained(<model_dir>/prott5/)``.

A single CustomSourceConfig populates both into one target dir (no single wrapper
covers "HF-flat + tar.gz subtree -> one flat dir"); the engine then caches the
whole tree to R2 atomically. Both variants share one R2 prefix, so we always
fetch the full set to avoid partial-cache misses.
"""

import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Optional

from models.abodybuilder3.schema import AbodyBuilder3Params
from models.commons.core.logging import get_logger
from models.commons.storage.acquisition import (
    AcquisitionConfig,
    AcquisitionStrategy,
    CacheConfig,
    CustomSourceConfig,
    R2OnlyConfig,
)
from models.commons.storage.download_helpers import download_with_fallback
from models.commons.storage.downloads import get_model_dir_util

logger = get_logger(__name__)

# Zenodo record 11354577 (Exscientia/abodybuilder3). output.tar.gz holds the
# trained structure-module checkpoints (~440 MB).
ZENODO_OUTPUT_TAR_URL = (
    "https://zenodo.org/api/records/11354577/files/output.tar.gz/content"
)

# ProtT5 language model used by the LANGUAGE variant (loaded flat via
# transformers from_pretrained). Restrict to the PyTorch + tokenizer files so we
# skip the TF/Flax/ONNX duplicates in the repo.
PROTT5_HF_REPO_ID = "Rostlab/prot_t5_xl_uniref50"
PROTT5_ALLOW_PATTERNS = ["*.json", "*.model", "pytorch_model.bin"]

REQUIRED_FILES = [
    "plddt-loss/best_second_stage.ckpt",
    "language-loss/best_second_stage.ckpt",
    "prott5/config.json",
    "prott5/pytorch_model.bin",
    "prott5/spiece.model",
]


def get_model_dir():

    return get_model_dir_util(
        base_model_slug=AbodyBuilder3Params.base_model_slug,
        params_version=AbodyBuilder3Params.params_version,
    )


def _download_checkpoints_from_zenodo(target_dir: Path) -> None:
    """Download Zenodo output.tar.gz and extract the ``*-loss`` checkpoints flat.

    Extraction is robust to the archive's root prefix: any member ending in
    ``-loss/best_second_stage.ckpt`` is placed at ``<target_dir>/<loss_dir>/...``.
    """
    import requests

    logger.info("Downloading AbodyBuilder3 checkpoints from Zenodo...")
    with tempfile.TemporaryDirectory(prefix="abb3_zenodo_") as tmp:
        tar_path = Path(tmp) / "output.tar.gz"
        with requests.get(ZENODO_OUTPUT_TAR_URL, stream=True, timeout=1800) as resp:
            resp.raise_for_status()
            with open(tar_path, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=8 * 1024 * 1024):
                    if chunk:
                        fh.write(chunk)

        extracted = 0
        with tarfile.open(tar_path, "r:gz") as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                if not member.name.endswith("-loss/best_second_stage.ckpt"):
                    continue
                loss_dir = Path(member.name).parent.name  # e.g. "plddt-loss"
                dest = target_dir / loss_dir / "best_second_stage.ckpt"
                dest.parent.mkdir(parents=True, exist_ok=True)
                src = tar.extractfile(member)
                if src is None:
                    continue
                with src, open(dest, "wb") as out:
                    shutil.copyfileobj(src, out)
                logger.info("  Extracted %s", dest.relative_to(target_dir))
                extracted += 1

        if extracted == 0:
            raise RuntimeError(
                "No '*-loss/best_second_stage.ckpt' checkpoints found in "
                f"{ZENODO_OUTPUT_TAR_URL}"
            )


def _download_prott5(target_dir: Path) -> None:
    """Download ProtT5 weights flat into ``<target_dir>/prott5/`` from HuggingFace."""
    from huggingface_hub import snapshot_download

    prott5_dir = target_dir / "prott5"
    prott5_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Downloading ProtT5 (%s) into prott5/ ...", PROTT5_HF_REPO_ID)
    snapshot_download(
        repo_id=PROTT5_HF_REPO_ID,
        local_dir=str(prott5_dir),
        allow_patterns=PROTT5_ALLOW_PATTERNS,
    )
    # Drop the huggingface_hub bookkeeping dir so it is not cached to R2.
    cache_meta = prott5_dir / ".cache"
    if cache_meta.exists():
        shutil.rmtree(cache_meta, ignore_errors=True)


def _download_abodybuilder3_assets(target_dir: Path, **_kwargs) -> dict:
    """CustomSourceConfig acquisition_fn: populate the full flat asset tree."""
    target_dir.mkdir(parents=True, exist_ok=True)
    _download_checkpoints_from_zenodo(target_dir)
    _download_prott5(target_dir)
    return {
        "source": "zenodo_and_huggingface",
        "zenodo_url": ZENODO_OUTPUT_TAR_URL,
        "prott5_repo": PROTT5_HF_REPO_ID,
    }


def download_model_assets(
    base_model_slug: str,
    params_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
):
    """Download AbodyBuilder3 assets: R2 primary, Zenodo + HuggingFace fallback."""

    model_dir = get_model_dir_util(
        base_model_slug=base_model_slug,
        params_version=params_version,
        sub_path=sub_path,
    )

    # Primary: marker-gated R2 read (no write — reading, not caching).
    primary_config = AcquisitionConfig(
        strategy=AcquisitionStrategy.R2_ONLY,
        target_dir=model_dir,
        cache_config=CacheConfig(enable_r2_cache=False),
        r2_config=R2OnlyConfig(
            base_model_slug=base_model_slug,
            params_version=params_version,
            model_variant=None,  # AbodyBuilder3 has no variant in the path
            sub_path=sub_path,
        ),
    )

    # Fallback: download both upstream sources, then cache the tree to R2.
    fallback_config = AcquisitionConfig(
        strategy=AcquisitionStrategy.CUSTOM,
        target_dir=model_dir,
        cache_config=CacheConfig(enable_r2_cache=True),
        custom_config=CustomSourceConfig(
            acquisition_fn=_download_abodybuilder3_assets,
            name="abodybuilder3_zenodo_hf",
            description="Zenodo checkpoints + ProtT5 (Rostlab/prot_t5_xl_uniref50)",
        ),
    )

    result = download_with_fallback(
        primary_config=primary_config,
        fallback_config=fallback_config,
    )

    if not result.success:
        raise RuntimeError(f"Model download failed: {result.error_message}")

    if result.cache_hit:
        logger.info("Downloaded AbodyBuilder3 assets from R2 cache")
    else:
        logger.info(
            "Downloaded %s files from source (cached to R2)", result.files_downloaded
        )

    return result.actual_model_path or result.target_dir
