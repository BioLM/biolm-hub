"""Query Modal for which model apps are currently deployed.

Powers the catalog's deployed (active) vs. undeployed (greyed-out) distinction.
The check is **best-effort**: if it can't run (no ``modal`` CLI on PATH, no
credentials, an API error, or an unexpected CLI schema), it returns ``None`` so
callers can show models with an *unknown* status rather than wrongly claiming
everything is undeployed.

It shells out to ``modal app list --json`` (read-only, tied to ``modal==1.3.5``)
and treats an app as deployed when its row's ``State`` is ``"deployed"`` (the app
name is the row's ``Description``). Results are cached briefly so repeated catalog
page loads don't spawn a ``modal`` subprocess per request.
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from gateway.model_discovery import ModelMapper
from models.commons.core.logging import get_logger

logger = get_logger(__name__)

# Short cache so rapid catalog navigation doesn't spawn a subprocess per request.
_CACHE_TTL_SECONDS = 8.0
_cache: dict[Optional[str], tuple[float, Optional[set[str]]]] = {}


def _modal_executable() -> str:
    """Path to the ``modal`` CLI — prefer the one next to the running interpreter.

    When invoked via ``.venv/bin/bm`` the venv isn't on PATH, so a bare ``modal``
    would not resolve; ``modal`` lives alongside ``python`` in the same bin dir.
    Falls back to ``"modal"`` on PATH otherwise.
    """
    candidate = Path(sys.executable).parent / "modal"
    return str(candidate) if candidate.exists() else "modal"


def get_deployed_app_names(environment: Optional[str] = None) -> Optional[set[str]]:
    """Return the set of Modal app names currently in the ``deployed`` state.

    Args:
        environment: Modal environment to query (``-e``). Defaults to the active
            profile / ``MODAL_ENVIRONMENT`` when None.

    Returns:
        A set of deployed app names, or ``None`` if the query could not be run /
        the CLI schema was unexpected (so the caller can distinguish "couldn't
        determine" from "none deployed"). Cached for a few seconds per environment.
    """
    cached = _cache.get(environment)
    if cached is not None and (time.monotonic() - cached[0]) < _CACHE_TTL_SECONDS:
        return cached[1]

    result = _query_deployed_app_names(environment)
    _cache[environment] = (time.monotonic(), result)
    return result


def _query_deployed_app_names(environment: Optional[str]) -> Optional[set[str]]:
    cmd = [_modal_executable(), "app", "list", "--json"]
    if environment:
        cmd += ["-e", environment]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, check=True
        )
        rows = json.loads(proc.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as e:
        stderr = getattr(e, "stderr", "") or ""
        logger.warning("Could not query deployed Modal apps (%s): %s %s", cmd[0], e, stderr)
        return None

    if not isinstance(rows, list):
        logger.warning("Unexpected `modal app list --json` output (not a list).")
        return None

    # Guard against a CLI schema change: if rows exist but none expose a
    # `Description`, treat it as unknown (None) rather than wrongly reporting
    # nothing as deployed — the one failure mode the None sentinel exists to avoid.
    if rows and not any(isinstance(r, dict) and r.get("Description") for r in rows):
        logger.warning(
            "`modal app list --json` rows have no 'Description'; CLI schema may have changed."
        )
        return None

    return {
        row["Description"]
        for row in rows
        if isinstance(row, dict)
        and row.get("State") == "deployed"
        and row.get("Description")
    }


def get_deployment_status(
    model_mapper: ModelMapper, environment: Optional[str] = None
) -> dict[str, Optional[bool]]:
    """Map each public model slug → deployed status.

    Returns a dict ``{public_slug: True | False | None}`` where ``True`` means the
    variant's Modal app is deployed, ``False`` means it isn't, and ``None`` means
    the deployment query couldn't run (status unknown — don't grey it out).
    """
    deployed = get_deployed_app_names(environment)
    status: dict[str, Optional[bool]] = {}
    for public_slug, variant_info in model_mapper.get_all_variant_mappings().items():
        if deployed is None:
            status[public_slug] = None
        else:
            status[public_slug] = variant_info["modal_app_name"] in deployed
    return status
