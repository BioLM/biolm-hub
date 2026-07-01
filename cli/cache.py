"""``bh cache`` — inspect response-caching configuration.

Response caching has two tiers — a short-term ``modal.Dict`` cache and a
long-term gzip cache in R2 — and **both are OFF by default**. Caching is a
*deploy-time* setting: it is controlled by the ``BIOLM_CACHE_ENABLED``
environment variable, read inside each deployed container (and the gateway), so
there is no local cache state to toggle here.

To turn caching on for a deployment, bake the flag in at deploy time:

    bh deploy esm2 --cache          # one-off
    BIOLM_CACHE_ENABLED=1 bh deploy esm2   # equivalent

``bh cache status`` reports whether the next ``bh deploy`` (in this shell) would
bake caching in, and explains how to change it.
"""

import os

import typer
from rich.console import Console

console = Console()

cache_app = typer.Typer(
    help="Inspect response-caching configuration (off by default).",
    invoke_without_command=True,
    no_args_is_help=False,
    add_completion=False,
)

# Mirrors models.commons.util.config.cache_enabled — kept local so `bh cache`
# stays import-light (no modal import just to read one env var).
_TRUTHY = {"1", "true", "yes"}


def _enabled() -> bool:
    return os.getenv("BIOLM_CACHE_ENABLED", "").strip().lower() in _TRUTHY


def _show_status() -> None:
    if _enabled():
        console.print(
            "Response caching: [green]ON[/green] for the next `bh deploy` in this "
            f"shell [dim](BIOLM_CACHE_ENABLED={os.environ['BIOLM_CACHE_ENABLED']})[/dim]"
        )
    else:
        console.print(
            "Response caching: [yellow]OFF[/yellow] [dim](default; "
            "BIOLM_CACHE_ENABLED unset)[/dim]"
        )

    console.print(
        "\n[dim]Caching is a deploy-time setting with two tiers (modal.Dict "
        "short-term + R2 long-term), both off by default. Enable it for a "
        "deployment with:[/dim]\n"
        "  [cyan]bh deploy <model> --cache[/cyan]\n"
        "[dim]Disable (the default) with [/dim][cyan]--no-cache[/cyan][dim], or "
        "set BIOLM_CACHE_ENABLED in your environment before deploying.[/dim]"
    )


@cache_app.callback()
def _default(ctx: typer.Context) -> None:
    """Show cache status when `bh cache` is run with no subcommand."""
    if ctx.invoked_subcommand is None:
        _show_status()


@cache_app.command("status")
def status() -> None:
    """Show whether response caching would be enabled for a deployment."""
    _show_status()
