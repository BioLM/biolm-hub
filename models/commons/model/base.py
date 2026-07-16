import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import modal


def _model_source_dir(cls: type) -> Path:
    """Locate the running model's own directory (holding its KG files), from inside its container.

    Prefer the ``_BIOLM_MODEL_SLUG`` env var baked into every model image by the source layer —
    ``inspect``/``sys.modules`` are unreliable here because Modal runs the app as ``__main__`` via
    its own entrypoint, so the class's ``__file__`` points at the runner, not ``app.py``. As a
    fallback (e.g. an older image without the env var) the source layer copies exactly one model
    directory alongside ``commons``, so the model's dir is the sole non-commons dir with a
    ``sources.yaml``.
    """
    from models.commons.catalog.knowledge import MODELS_DIR, model_dir_for_slug

    slug = os.environ.get("_BIOLM_MODEL_SLUG")
    if slug:
        return model_dir_for_slug(slug)

    candidates = [
        d
        for d in sorted(MODELS_DIR.iterdir())
        if d.is_dir()
        and d.name != "commons"
        and not d.name.startswith(("_", "."))
        and (d / "sources.yaml").exists()
    ]
    if len(candidates) == 1:
        return candidates[0]
    raise RuntimeError(
        f"cannot locate the model source directory for {cls.__name__!r} "
        f"(set _BIOLM_MODEL_SLUG); candidates={[d.name for d in candidates]}"
    )


class ModelMixin:
    """Base class for Modal model container classes.

    Exposes the lightweight liveness/health Modal methods that the framework
    provides on every model. Subclasses define their own ``@modal.enter`` setup
    and (optionally) ``@modal.exit`` cleanup.

    Usage::

        @app.cls(...)
        class MyModel(ModelMixin):
            @modal.enter()
            def setup_model(self):
                ...
    """

    @modal.method()
    def is_live(self) -> int:
        """Liveness probe — returns 1 once the container is serving."""
        return 1

    @modal.method()
    def healthy(self) -> dict[str, str]:
        """Lightweight health check for the container."""
        return {
            "status": "healthy",
            "class_name": self.__class__.__name__,
        }

    @modal.method()
    def knowledge_graph(self, fmt: str = "json") -> dict[str, Any] | str:
        """Return this model's knowledge graph — what it is, how/when (and when not) to use it.

        A self-describing endpoint every model gets for free: it reads the model's own
        ``sources.yaml`` / ``comparison.yaml`` / ``README.md`` / ``MODEL.md`` / ``BIOLOGY.md``
        (baked into the container image) and returns the same typed payload the gateway
        ``/knowledge`` route serves. ``fmt="json"`` (default) returns the structured object;
        ``fmt="md"`` returns one normalized Markdown document.
        """
        from models.commons.catalog.knowledge import load_model_knowledge

        knowledge = load_model_knowledge(_model_source_dir(type(self)))
        if fmt == "md":
            return knowledge.to_markdown()
        return knowledge.model_dump(mode="json")


class ModelMixinSnap(ModelMixin):
    """Base class for containers that use Modal memory snapshots.

    Preserves the snapshot-enter ordering: Modal runs ``@modal.enter(snap=True)``
    methods in alphabetical order, so ``a_snapshot_enter`` runs first and
    ``z_snapshot_enter`` runs last, bracketing a subclass's own
    ``setup_model(snap=True)``. The hooks are no-ops; ``save_snapshot_uptime`` is
    retained as a no-op because some models call it explicitly from their setup.
    """

    def save_snapshot_uptime(self) -> None:
        """Snapshot-uptime hook (no-op; retained for subclasses that call it)."""

    @modal.enter(snap=True)
    def a_snapshot_enter(self) -> None:
        """First snapshot-enter hook (no-op; reserved for framework lifecycle)."""

    @modal.enter(snap=True)
    def z_snapshot_enter(self) -> None:
        """Last snapshot-enter hook (no-op; reserved for framework lifecycle)."""
        self.save_snapshot_uptime()


@dataclass
class ModelParams:
    """Base class for defining model parameters.

    Define model names with same spelling as found in the publications.
    """

    display_name: (
        str  # Full, human-readable name of the model (eg: "ESM Inverse Folding")
    )
    base_model_slug: str  # Identifier used in API URLs (eg: "esm-if1")
    log_identifier: str  # Identifier used in logs and print statements (eg: "ESM-IF1")

    """ Define model checkpoint parameters """
    weights_version: str

    """ Define model parameters """
    batch_size: int
    max_sequence_len: Optional[int]
    # add other model parameters to your inheriting class
