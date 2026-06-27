import typer
from rich.console import Console
from rich.layout import Layout
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from cli.deploy import deploy_cmd
from cli.kb import kb_app
from cli.r2 import r2_app

"""
BioLM-Modal Command Line Interface

A suite of tools for working with BioLM-Modal models and infrastructure.
"""


console = Console()
app = typer.Typer(
    name="bm",
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
    """BioLM-Modal is a platform for serving BioLM models on Modal."""
    pass


# Mount subcommands
app.add_typer(r2_app, name="r2")
app.add_typer(kb_app, name="kb")

# Mount the deploy command directly
app.command("deploy")(deploy_cmd)


def display_cli_help() -> None:
    """Display a rich formatted help message."""
    layout = Layout()

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
    commands_table.add_row("r2", "Manage Cloudflare R2 storage resources")
    commands_table.add_row("kb", "Manage model knowledge bases")

    storage_table = Table(show_header=True, box=None, padding=(0, 2))
    storage_table.add_column("Command", style="cyan")
    storage_table.add_column("Description", style="green")

    storage_panel = Panel(
        storage_table,
        title="[bold]Storage",
        border_style="blue",
        padding=(1, 2),
    )
    commands_table.add_row("r2 ls", "List contents of R2 buckets")
    commands_table.add_row("r2 cp", "Copy files between local and R2")
    commands_table.add_row("r2 cat", "Display contents of a text file from R2")
    commands_table.add_row("r2 du", "Calculate folder size in R2 storage")
    commands_table.add_row("r2 rm", "Remove files and directories from R2")
    commands_table.add_row(
        "r2 download-outputs", "Download test fixture outputs for a model"
    )
    commands_table.add_row("kb status", "Show knowledge base completion status")
    commands_table.add_row("kb validate", "Validate sources.yaml schema")
    commands_table.add_row("kb sources", "Display sources.yaml summary for a model")
    commands_table.add_row("kb matrix", "Generate MODEL_COMPARISON_MATRIX.md")
    commands_table.add_row("kb missing", "Report papers with pending R2 uploads")

    footer = Padding(
        Text(
            "Run 'bm COMMAND --help' for more information on a command.", style="italic"
        ),
        (1, 0),
    )

    layout.split(
        Layout(header), Layout(commands_panel), Layout(storage_panel), Layout(footer)
    )

    console.print(layout)


@app.command(name="help")
def help_cmd() -> None:
    """Show this help message."""
    display_cli_help()


if __name__ == "__main__":
    app()
