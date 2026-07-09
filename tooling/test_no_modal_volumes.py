"""CI guard: no model mounts a Modal Volume / NFS / cloud-bucket mount.

Modal-free (scans source text), so it runs in the unit tier. See
``tooling/check_no_modal_volumes.py`` for the rationale and a CLI.
"""

from __future__ import annotations

from tooling.check_no_modal_volumes import scan


def test_no_model_uses_modal_volumes() -> None:
    violations = scan()
    assert not violations, (
        "out-of-scope Modal persistent-storage usage (see CONTRIBUTING.md → "
        '"Scope — bounded assets only"):\n' + "\n".join(violations)
    )
