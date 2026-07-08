from dataclasses import dataclass
from typing import Optional

import modal


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
