"""``bm setup`` — check your environment and tell you exactly what to configure.

Verifies the prerequisites for deploying models to **your own** Modal workspace
and reports, in one place, what is ready and what (if anything) you still need to
do. It performs only local, network-free checks — it never deploys or bills.

What it checks:
  • **Modal authentication** (required) — a token in ``~/.modal.toml`` or the
    ``MODAL_TOKEN_ID`` / ``MODAL_TOKEN_SECRET`` environment variables.
  • **Cloudflare R2 credentials** (optional) — only needed to use the local
    ``bm r2`` browser or to cache weights/responses into *your own* bucket via
    ``BIOLM_R2_BUCKET``. Public model weights are served from a read-only public
    bucket, so the happy path ("deploy esm2 and run inference") needs nothing
    beyond a Modal account.

Exits non-zero if a *required* prerequisite (Modal auth) is missing, so it can
gate scripts and CI.
"""

import os

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

# Default read-only public bucket (mirrors models.commons.util.config). Read
# directly here so `bm setup` stays import-light and modal-free.
_DEFAULT_BUCKET = "biolm-public"


def _modal_status() -> tuple[bool, str]:
    """Return (configured, human-readable detail) for Modal auth — no network.

    Honors both the env-var path (``MODAL_TOKEN_ID``/``MODAL_TOKEN_SECRET``,
    used by CI) and a token stored in ``~/.modal.toml`` via ``modal.config``.
    """
    if os.getenv("MODAL_TOKEN_ID") and os.getenv("MODAL_TOKEN_SECRET"):
        env = os.getenv("MODAL_ENVIRONMENT") or "(workspace default)"
        return True, f"authenticated via MODAL_TOKEN_ID/SECRET · environment={env}"

    try:
        from modal.config import config, user_config_path

        # config.get() resolves the active profile *and* MODAL_* env vars. Both
        # halves of the token must be present — a lone MODAL_TOKEN_ID would
        # still fail to deploy.
        if config.get("token_id") and config.get("token_secret"):
            env = (
                os.getenv("MODAL_ENVIRONMENT")
                or config.get("environment")
                or "(workspace default)"
            )
            return True, f"token in {user_config_path} · environment={env}"
    except Exception:
        # modal.config internals shifted, or modal isn't importable — treat as
        # unconfigured and let the guidance below take over.
        pass

    return False, ""


def _r2_local_status() -> tuple[bool, dict[str, bool]]:
    """Return (all-present, per-var presence) for the local ``bm r2`` creds.

    These power the *local* R2 client only (``bm r2`` browsing and caching to
    your own bucket). They are unrelated to the Modal-side ``cloudflare-r2``
    secret used inside deployed containers. ``AWS_REGION`` is optional.
    """
    present = {
        "AWS_ACCESS_KEY_ID": bool(os.getenv("AWS_ACCESS_KEY_ID")),
        "AWS_SECRET_ACCESS_KEY": bool(os.getenv("AWS_SECRET_ACCESS_KEY")),
        "R2_ENDPOINT": bool(os.getenv("R2_ENDPOINT")),
    }
    return all(present.values()), present


def setup_cmd() -> None:
    """Check your Modal + R2 configuration and report exactly what to fix."""
    modal_ok, modal_detail = _modal_status()
    r2_ok, r2_present = _r2_local_status()
    bucket = os.getenv("BIOLM_R2_BUCKET", _DEFAULT_BUCKET)

    table = Table(show_header=True, box=None, padding=(0, 2))
    table.add_column("", width=2)
    table.add_column("Check", style="bold")
    table.add_column("Status")

    # Modal — required.
    if modal_ok:
        table.add_row("✅", "Modal auth", f"[green]ready[/green] — {modal_detail}")
    else:
        table.add_row("❌", "Modal auth", "[red]not configured[/red] (required)")

    # R2 local creds — optional.
    if r2_ok:
        table.add_row(
            "✅",
            "R2 (local)",
            "[green]configured[/green] — `bm r2` browsing enabled",
        )
    else:
        missing = ", ".join(k for k, v in r2_present.items() if not v)
        table.add_row(
            "ℹ️ ",
            "R2 (local)",
            f"[dim]optional[/dim] — not set ({missing})",
        )

    table.add_row("", "Model bucket", f"{bucket} [dim](read-only public weights)[/dim]")

    console.print(Panel(table, title="[bold]bm setup[/bold]", border_style="blue"))

    # Actionable guidance for anything that isn't ready.
    if not modal_ok:
        console.print(
            Panel(
                "Deploying models needs a [bold]Modal[/bold] account (free tier works).\n\n"
                "  1. [cyan]pip install modal[/cyan]   "
                "[dim](already installed via `make install`)[/dim]\n"
                "  2. [cyan]modal token new[/cyan]     "
                "[dim](opens your browser to authenticate)[/dim]\n\n"
                "Then re-run [cyan]bm setup[/cyan].",
                title="[red]Modal not configured[/red]",
                border_style="red",
            )
        )

    if not r2_ok:
        console.print(
            "[dim]R2 is optional. The default bucket "
            f"([bold]{bucket}[/bold]) is read-only and serves public weights "
            "with no credentials. Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY "
            "and R2_ENDPOINT only if you want to use `bm r2` or cache into your "
            "own bucket via BIOLM_R2_BUCKET.[/dim]"
        )

    if modal_ok:
        console.print("\n[green]You're ready.[/green] Try: [cyan]bm deploy esm2[/cyan]")
    else:
        # Non-zero exit so scripts/CI can gate on a clean setup.
        raise typer.Exit(1)
