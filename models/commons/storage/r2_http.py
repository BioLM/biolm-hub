"""Unauthenticated HTTP reads of cached model weights from the public R2 bucket.

When no R2 (S3) credentials are present, cached model weights are read anonymously
over HTTPS from the bucket's Cloudflare "Public Development URL" (r2.dev) instead of
the signed S3 API. This is what makes the "no credentials beyond Modal" happy path
real for read-only consumers of the public OSS bucket.

Why a separate read path (not just an unsigned boto3 client): r2.dev serves
single-object GETs but **cannot LIST** a prefix, while the S3 read path enumerates
files with `list_objects_v2`. So this reader drives the fetch from the
`.r2_manifest.json` object — written by the atomic upload, it lists every cached
file's relative path under the prefix — rather than from an S3 LIST. The completion
marker (`.r2_cache_complete`) is the same miss/hit gate as the S3 path.

The same anonymous path also serves small JSON objects — the golden/input test
fixtures read by the integration harness — via ``read_json_via_http`` (the
credential-less counterpart of ``r2.read_json_from_r2``), so ``pytest -m integration``
runs against the public OSS bucket with no S3 credentials.

This module is READ-ONLY by design. Writes/self-population always go through the
credentialed S3 path (CI only) — see r2_utils.upload_to_r2_atomic.
"""

import json
from contextlib import closing
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from models.commons.core.logging import get_logger
from models.commons.storage.r2_utils import R2Utils

logger = get_logger(__name__)

# (connect, read) timeouts in seconds. The read timeout is generous because a single
# GET may stream a multi-GB weight file (mirrors the S3 client's 600s read timeout).
_HTTP_TIMEOUT = (30, 600)
_CHUNK_SIZE = 1024 * 1024  # 1MB streaming chunks

# r2.dev is explicitly rate-limited (see config.r2_public_url), so retry transient
# 429/5xx and connection errors with backoff — parity with the S3 client's adaptive
# retries. 404 is NOT in the forcelist: it stays a clean cache miss, not a retry.
_RETRY = Retry(
    total=5,
    connect=5,
    read=5,
    backoff_factor=0.5,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset({"GET"}),
    raise_on_status=False,
)


def _session() -> requests.Session:
    """A requests Session with bounded retry/backoff for the rate-limited endpoint."""
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=_RETRY)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _object_url(public_url: str, r2_prefix: str, rel_key: str) -> str:
    """Build the public HTTPS URL for one object: {base}/{prefix}/{rel_key}.

    The prefix and key are URL-encoded (preserving `/` separators) so weight
    filenames containing spaces or URL-structural characters (`#`, `?`, `%`) resolve
    to the correct object instead of being silently truncated/misparsed.
    """
    prefix = quote(r2_prefix.strip("/"), safe="/")
    key = quote(rel_key.lstrip("/"), safe="/")
    return f"{public_url.rstrip('/')}/{prefix}/{key}"


def _key_url(public_url: str, key: str) -> str:
    """Build the public HTTPS URL for an object addressed by its full bucket key.

    Unlike ``_object_url`` (which joins a model prefix with a relative weight path),
    JSON goldens/inputs are addressed by a single absolute bucket key, e.g.
    ``biolm-hub/test-data/models/<slug>/predict_input.json``. The key is URL-encoded
    (preserving ``/`` separators) with the same safety as the weights read path.
    """
    return f"{public_url.rstrip('/')}/{quote(key.lstrip('/'), safe='/')}"


def _http_get(session: requests.Session, url: str) -> Optional[requests.Response]:
    """GET a URL (streamed). Return the response, or None on 404. Raise on other errors.

    The caller is responsible for closing/consuming the returned response.
    """
    resp = session.get(url, stream=True, timeout=_HTTP_TIMEOUT)
    if resp.status_code == 404:
        resp.close()
        return None
    resp.raise_for_status()
    return resp


def _within(base: Path, candidate: Path) -> bool:
    """True if `candidate` is `base` or lives under it (defense against path escape)."""
    try:
        candidate.relative_to(base)
        return True
    except ValueError:
        return False


def restore_weights_via_http(target_dir: Path, r2_prefix: str, public_url: str) -> bool:
    """Restore cached model weights from the public bucket over anonymous HTTPS.

    Mirrors the miss/hit semantics of the S3 cache read: returns True only on a
    complete restore, and False on a cache miss (no completion marker, or no
    manifest to enumerate from) so the caller falls back to the original source.

    Note: the completion-marker timeout (`cache_timeout_hours` on the S3 path) is
    intentionally NOT enforced here — public weights are immutable, so an existence
    gate is sufficient.

    Args:
        target_dir: Local directory to restore weights into.
        r2_prefix: R2 key prefix for this model (no leading/trailing slash), as
            produced by R2Utils.get_r2_prefix_from_target_dir.
        public_url: Base r2.dev (or custom-domain) URL for the bucket.

    Returns:
        True on a complete restore; False on a cache miss.
    """
    target_root = target_dir.resolve()
    session = _session()
    try:
        # 1. Completion-marker gate — same as the S3 path: no marker => treat as miss.
        marker = _http_get(
            session, _object_url(public_url, r2_prefix, R2Utils.COMPLETION_MARKER)
        )
        if marker is None:
            logger.info(
                "No R2 completion marker at %s (public HTTP read) — cache miss",
                r2_prefix,
            )
            return False
        marker.close()

        # 2. The manifest is the only way to enumerate keys without an S3 LIST.
        manifest_resp = _http_get(
            session, _object_url(public_url, r2_prefix, R2Utils.MANIFEST_FILE)
        )
        if manifest_resp is None:
            logger.warning(
                "R2 completion marker present but no %s at %s — cannot enumerate "
                "cached files over public HTTP (r2.dev has no LIST); cache miss",
                R2Utils.MANIFEST_FILE,
                r2_prefix,
            )
            return False
        with closing(manifest_resp):
            manifest = json.loads(manifest_resp.content.decode("utf-8"))

        # 3. GET each manifested file by key (idempotent on size — skip files already
        #    present locally at the manifested size).
        target_dir.mkdir(parents=True, exist_ok=True)
        total = len(manifest)
        downloaded = 0
        for idx, (rel_path, meta) in enumerate(manifest.items(), 1):
            dest = (target_dir / rel_path).resolve()
            # Defense-in-depth: a crafted manifest key (absolute or `../`) must not
            # write outside target_dir. The bucket is BioLM-controlled, but cheap.
            if not _within(target_root, dest):
                logger.error(
                    "Manifest key escapes target dir, refusing restore: %r", rel_path
                )
                return False

            expected_size = meta.get("size") if isinstance(meta, dict) else None
            if (
                dest.exists()
                and expected_size is not None
                and dest.stat().st_size == expected_size
            ):
                continue

            resp = _http_get(session, _object_url(public_url, r2_prefix, rel_path))
            if resp is None:
                logger.error(
                    "Manifest lists '%s' but it 404s under %s — incomplete public cache",
                    rel_path,
                    r2_prefix,
                )
                return False

            dest.parent.mkdir(parents=True, exist_ok=True)
            logger.info("  [%s/%s] 📥 (public HTTP) %s", idx, total, rel_path)
            with closing(resp), open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=_CHUNK_SIZE):
                    f.write(chunk)
            downloaded += 1

        logger.info(
            "✅ Restored %s files from the public R2 bucket over HTTP (%s new, %s prefix)",
            total,
            downloaded,
            r2_prefix,
        )
        return True
    finally:
        session.close()


def read_json_via_http(public_url: str, key: str) -> Any:
    """Read and JSON-parse a single object from the public bucket over anonymous HTTPS.

    The credential-less counterpart of ``r2.read_json_from_r2``: instead of a signed S3
    ``GetObject`` it GETs ``{public_url}/{key}`` from the bucket's r2.dev public URL.
    Used to read golden/input test fixtures so ``pytest -m integration`` runs against
    the public OSS bucket with only ``BIOLM_R2_PUBLIC_URL`` (no ``AWS_*``/``R2_ENDPOINT``).

    Args:
        public_url: Base r2.dev (or custom-domain) URL for the bucket.
        key: Full object key within the bucket (e.g. ``biolm-hub/test-data/...``).

    Returns:
        The JSON-parsed content (typically a dict or list).

    Raises:
        FileNotFoundError: on a 404, or any transport/parse error — mirroring
            ``read_json_from_r2``'s not-found contract so callers see a uniform failure.
    """
    url = _key_url(public_url, key)
    session = _session()
    try:
        resp = _http_get(session, url)
        if resp is None:
            raise FileNotFoundError(
                f"{key} not found in the public R2 bucket (404 at {url})"
            )
        with closing(resp):
            return json.loads(resp.content.decode("utf-8"))
    except FileNotFoundError:
        raise
    except Exception as e:
        raise FileNotFoundError(
            f"Error reading {key} from the public R2 bucket over HTTP: {e}"
        ) from e
    finally:
        session.close()
