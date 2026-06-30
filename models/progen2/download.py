"""Download module for ProGen2 weights.

R2 cache first; on a miss fetch the *original* Salesforce ProGen2 checkpoints and
cache them back to R2 so ``git clone -> deploy`` self-populates.

Source of truth
---------------
The fallback streams the original Salesforce release archives from Google Cloud
Storage (public, BSD-3-Clause):

    https://storage.googleapis.com/sfr-progen-research/checkpoints/progen2-<v>.tar.gz

Each archive is a flat tar of ``config.json`` + ``pytorch_model.bin`` — exactly
the per-variant weight files the *bundled* loader expects
(``external/sample_utils.create_model`` -> ``ProGenForCausalLM.from_pretrained``).
The original ``config.json`` carries the correct per-variant ``n_embd`` and
``vocab_size`` (32), so no config patching and no ``trust_remote_code`` swap is
needed: the bundled architecture and its outputs are preserved exactly.

The shared ``tokenizer.json`` is *not* in the checkpoint archives; it is fetched
once from the Salesforce ProGen GitHub repo (same BSD-3-Clause release) — see
``PROGEN2_TOKENIZER_URL``.

(The ``hugohrban/progen2-*`` HF mirrors were rejected: the ``oas`` and ``BFD90``
configs omit ``n_embd``/``vocab_size`` entirely — the bundled ProGenConfig would
silently fall back to its 4096/50400 defaults and crash on a weight-shape
mismatch — and they ship ``model.safetensors`` rather than the
``pytorch_model.bin`` the loader / ``required_files`` expect.)

On-disk layout
--------------
The loader reads, under ``model_dir`` (= ``<...>/checkpoints/``):

  - ``progen2_<type>/config.json``
  - ``progen2_<type>/pytorch_model.bin``
  - ``tokenizer.json``           (shared across all variants)

Caching strategy
----------------
All four variants share one R2 prefix (``<...>/checkpoints/``) and one
completion marker, so on a cache miss we fetch the *full* set of variants before
caching — a partial cache would mark the prefix "complete" and then 404 the
sibling variants. The R2-primary read is filtered to just the requested variant
(+ the shared tokenizer) so each variant image stays lean on the steady-state
cache-hit path.
"""

import os
import shutil
import tarfile
from typing import Optional

from models.commons.core.logging import get_logger
from models.commons.storage.acquisition import (
    AcquisitionConfig,
    AcquisitionStrategy,
    CacheConfig,
    CustomSourceConfig,
    R2OnlyConfig,
    ValidationConfig,
)
from models.commons.storage.download_helpers import (
    download_with_fallback,
    extract_model_variant,
)
from models.commons.storage.downloads import get_model_dir_util
from models.progen2.schema import ProGen2ModelTypes, ProGen2Params

logger = get_logger(__name__)

# Public Salesforce ProGen2 checkpoint archives (BSD-3-Clause).
GCS_CHECKPOINT_BASE = "https://storage.googleapis.com/sfr-progen-research/checkpoints"

# The checkpoint archives ship only ``config.json`` + ``pytorch_model.bin``; the
# shared ``tokenizer.json`` lives in the Salesforce ProGen GitHub repo
# (BSD-3-Clause, same release) and is fetched once per build.
PROGEN2_TOKENIZER_URL = (
    "https://raw.githubusercontent.com/salesforce/progen/main/progen2/tokenizer.json"
)

# schema MODEL_TYPE value -> Salesforce archive token. Note the upstream archive
# for BFD90 is spelled in uppercase (``progen2-BFD90.tar.gz``).
_GCS_VARIANT_TOKEN = {
    ProGen2ModelTypes.OAS.value: "oas",
    ProGen2ModelTypes.MEDIUM.value: "medium",
    ProGen2ModelTypes.LARGE.value: "large",
    ProGen2ModelTypes.BFD90.value: "BFD90",
}

ALL_MODEL_TYPES = [e.value for e in ProGen2ModelTypes]


def get_model_dir():

    return get_model_dir_util(
        base_model_slug=ProGen2Params.base_model_slug,
        weights_version=ProGen2Params.weights_version,
        sub_path="checkpoints",
    )


def _fetch_tokenizer(target_dir) -> None:
    """Fetch the shared ``tokenizer.json`` to the root of ``target_dir``.

    The checkpoint archives do not bundle the tokenizer, so it is pulled once
    from the Salesforce ProGen GitHub repo (BSD-3-Clause).
    """
    import requests  # available in the Modal download layer (base_packages)

    dest = target_dir / "tokenizer.json"
    logger.info("Fetching ProGen2 tokenizer from %s", PROGEN2_TOKENIZER_URL)
    resp = requests.get(PROGEN2_TOKENIZER_URL, timeout=(30, 120))
    resp.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)


def _stream_progen2_archive(target_dir, model_type: str) -> None:
    """Stream one Salesforce ``.tar.gz`` and extract the per-variant weights.

    ``config.json`` and ``pytorch_model.bin`` land in ``progen2_<type>/``. The
    archive is streamed through ``tarfile`` directly off the socket (no temp
    ``.tar.gz`` on disk), so peak build disk is bounded by the extracted weights
    alone. (The shared ``tokenizer.json`` is fetched separately — it is not in
    the checkpoint archives.)
    """
    import requests  # available in the Modal download layer (base_packages)

    token = _GCS_VARIANT_TOKEN[model_type]
    url = f"{GCS_CHECKPOINT_BASE}/progen2-{token}.tar.gz"
    variant_dir = target_dir / f"progen2_{model_type}"
    variant_dir.mkdir(parents=True, exist_ok=True)

    # tar member basename -> destination on disk
    destinations = {
        "config.json": variant_dir / "config.json",
        "pytorch_model.bin": variant_dir / "pytorch_model.bin",
    }
    extracted: set[str] = set()

    logger.info("Streaming ProGen2 '%s' from %s", model_type, url)
    with requests.get(url, stream=True, timeout=(30, 600)) as resp:
        resp.raise_for_status()
        # The .gz is the file payload (Content-Type: application/x-tar), not a
        # transfer encoding — let tarfile do the gunzip, not urllib3.
        resp.raw.decode_content = False
        with tarfile.open(fileobj=resp.raw, mode="r|gz") as tar:
            for member in tar:
                if not member.isfile():
                    continue
                dest = destinations.get(os.path.basename(member.name))
                if dest is None:
                    continue
                src = tar.extractfile(member)
                if src is None:
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                with src, open(dest, "wb") as out:
                    shutil.copyfileobj(src, out, length=8 * 1024 * 1024)
                extracted.add(os.path.basename(member.name))

    # tokenizer.json may already exist from an earlier variant; only the
    # per-variant weight files are mandatory in this archive.
    missing = {"config.json", "pytorch_model.bin"} - extracted
    if missing:
        raise RuntimeError(
            f"ProGen2 '{model_type}' archive missing {sorted(missing)} (from {url})"
        )


def _download_all_progen2_assets(target_dir, **_kwargs) -> dict:
    """CustomSourceConfig acquisition_fn: populate every variant + tokenizer.

    Always fetches the full set because all variants share one R2 prefix /
    completion marker (see module docstring).
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    for model_type in ALL_MODEL_TYPES:
        _stream_progen2_archive(target_dir, model_type)
    _fetch_tokenizer(target_dir)
    return {
        "source": "salesforce_gcs",
        "base_url": GCS_CHECKPOINT_BASE,
        "variants": ALL_MODEL_TYPES,
    }


def download_model_assets(
    base_model_slug: str,
    weights_version: str,
    variant_config: Optional[dict] = None,
    sub_path: Optional[str] = None,
):
    """Download ProGen2 assets: filtered R2 primary, Salesforce GCS fallback."""

    # Extract MODEL_TYPE from variant_config
    model_type = extract_model_variant(variant_config, "MODEL_TYPE")
    derived_variant = f"progen2_{model_type}"

    model_dir = get_model_dir_util(
        base_model_slug=base_model_slug,
        weights_version=weights_version,
        sub_path=sub_path,
    )

    # R2 layout mirrors the on-disk layout: every variant under one
    # checkpoints/ prefix plus a shared tokenizer.json. Restore only the
    # requested variant (+ tokenizer) so the image stays lean.
    def progen2_filter_func(full_key: str) -> bool:
        if derived_variant in str(full_key):
            return True
        if full_key.endswith("tokenizer.json"):
            return True
        return False

    # Primary: marker-gated R2 read, filtered to this variant + shared tokenizer.
    primary_config = AcquisitionConfig(
        strategy=AcquisitionStrategy.R2_ONLY,
        target_dir=model_dir,
        cache_config=CacheConfig(enable_r2_cache=False),  # reading, not writing
        validation_config=ValidationConfig(
            required_files=[
                f"{derived_variant}/config.json",
                f"{derived_variant}/pytorch_model.bin",
                "tokenizer.json",
            ],
        ),
        r2_config=R2OnlyConfig(
            base_model_slug=base_model_slug,
            weights_version=weights_version,
            model_variant=None,  # path is just <slug>/<version>/checkpoints/
            sub_path=sub_path,
            filter_func=progen2_filter_func,
        ),
    )

    # Fallback: fetch ALL variants from the original Salesforce archives, then
    # cache the whole tree to R2. required_files enforces the full set BEFORE
    # caching so a partial download can never poison the shared completion marker.
    full_required: list[str] = []
    for mt in ALL_MODEL_TYPES:
        full_required.append(f"progen2_{mt}/config.json")
        full_required.append(f"progen2_{mt}/pytorch_model.bin")
    full_required.append("tokenizer.json")

    fallback_config = AcquisitionConfig(
        strategy=AcquisitionStrategy.CUSTOM,
        target_dir=model_dir,
        cache_config=CacheConfig(enable_r2_cache=True),
        validation_config=ValidationConfig(required_files=full_required),
        custom_config=CustomSourceConfig(
            acquisition_fn=_download_all_progen2_assets,
            name="progen2_salesforce_gcs",
            description=(
                "Original Salesforce ProGen2 checkpoints "
                "(config.json + pytorch_model.bin + tokenizer.json) from GCS"
            ),
        ),
    )

    result = download_with_fallback(
        primary_config=primary_config,
        fallback_config=fallback_config,
    )

    if not result.success:
        raise RuntimeError(f"Model download failed: {result.error_message}")

    if result.metadata.get("strategy") == "r2_only":
        logger.info(
            "ProGen2 '%s' restored from R2 (%s files)",
            model_type,
            result.files_downloaded,
        )
    else:
        logger.info(
            "ProGen2 assets fetched from Salesforce GCS and cached to R2 (%s files)",
            result.files_downloaded,
        )

    return result.actual_model_path or result.target_dir
