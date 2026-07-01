"""BioLM Models CLI (``bh``).

Command-line tools for deploying and running BioLM models on Modal.
"""

import typer
from rich.console import Console
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from cli.cache import cache_app
from cli.deploy import deploy_cmd
from cli.kb import kb_app
from cli.r2 import r2_app
from cli.serve import serve_cmd
from cli.setup import setup_cmd

console = Console()
app = typer.Typer(
    name="bh",
    help="BioLM command-line tools for model management and infrastructure.",
    no_args_is_help=True,
    add_completion=False,
)


def print_version(value: bool) -> None:
    if value:
        console.print("BioLM CLI version 0.1.0")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show version information.",
        callback=print_version,
        is_eager=True,
    ),
) -> None:
    """Command-line tools for deploying and running BioLM models on Modal."""
    pass


# Mount subcommands
app.add_typer(r2_app, name="r2")
app.add_typer(kb_app, name="kb")
app.add_typer(cache_app, name="cache")

# Mount the setup command (environment check / first-run guidance)
app.command("setup")(setup_cmd)

# Mount the deploy command directly
app.command("deploy")(deploy_cmd)

# Mount the serve command (local catalog web app)
app.command("serve")(serve_cmd)


def display_cli_help() -> None:
    """Display a rich formatted help message."""
    header = Panel(
        "BioLM Command Line Interface",
        style="bold blue",
        padding=(1, 2),
    )

    commands_table = Table(show_header=True, box=None, padding=(0, 2))
    commands_table.add_column("Command", style="cyan")
    commands_table.add_column("Description", style="green")

    commands_panel = Panel(
        commands_table,
        title="[bold]Commands",
        border_style="blue",
        padding=(1, 2),
    )
    commands_table.add_row("setup", "Check your Modal + R2 configuration")
    commands_table.add_row("deploy", "Deploy one or more models to Modal")
    commands_table.add_row("serve", "Launch the local catalog web app")
    commands_table.add_row("cache", "Inspect response-caching configuration")
    commands_table.add_row("r2", "Browse Cloudflare R2 storage (read-only)")
    commands_table.add_row("kb", "Manage model knowledge bases")

    storage_table = Table(show_header=True, box=None, padding=(0, 2))
    storage_table.add_column("Command", style="cyan")
    storage_table.add_column("Description", style="green")

    storage_panel = Panel(
        storage_table,
        title="[bold]Storage (read-only)",
        border_style="blue",
        padding=(1, 2),
    )
    storage_table.add_row("r2 ls", "List contents of R2 buckets")
    storage_table.add_row("r2 download", "Download files from R2 to local storage")
    storage_table.add_row("r2 cat", "Display contents of a text file from R2")
    storage_table.add_row("r2 du", "Calculate folder size in R2 storage")
    storage_table.add_row(
        "r2 download-outputs", "Download test fixture outputs for a model"
    )
    commands_table.add_row("kb status", "Show knowledge base completion status")
    commands_table.add_row("kb validate", "Validate sources.yaml schema")
    commands_table.add_row("kb sources", "Display sources.yaml summary for a model")

    footer = Padding(
        Text(
            "Run 'bh COMMAND --help' for more information on a command.", style="italic"
        ),
        (1, 0),
    )

    console.print(header)
    console.print(commands_panel)
    console.print(storage_panel)
    console.print(footer)


@app.command(name="help")
def help_cmd() -> None:
    """Show this help message."""
    display_cli_help()


if __name__ == "__main__":
    app()
