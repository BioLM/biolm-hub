"""
Knowledge Base CLI commands.

Provides tools for inspecting, validating, and managing the model knowledge base.
"""

from pathlib import Path
from typing import Any, Optional

import typer
import yaml
from rich.console import Console
from rich.table import Table

console = Console()
kb_app = typer.Typer(
    help="Manage model knowledge bases.",
    no_args_is_help=True,
)

# --- Constants ---
REPO_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = REPO_ROOT / "models"
SKIP_DIRS = {"commons", "scripts", "__pycache__", "dummy"}

# Valid enum values for schema validation
VALID_MOLECULE_TYPES = {
    "protein",
    "antibody",
    "nanobody",
    "tcr",
    "peptide",
    "dna",
    "rna",
    "ligand",
    "complex",
}
VALID_TASKS = {
    "structure_prediction",
    "inverse_folding",
    "embedding",
    "sequence_generation",
    "sequence_completion",
    "property_prediction",
    "sequence_classification",
    "annotation",
    "feature_extraction",
    "sequence_optimization",
    "stability_prediction",
    "utility",
}
VALID_REPO_TYPES = {"github", "huggingface", "nims", "pypi", "other"}

REQUIRED_FIELDS = {
    "model_slug",
    "display_name",
    "license",
    "molecule_types",
    "tasks",
    "primary_papers",
}
REQUIRED_PAPER_FIELDS = {"title", "year"}
REQUIRED_DOCS = {"README.md", "MODEL.md", "BIOLOGY.md"}


def _get_all_model_slugs() -> list[str]:
    """Get all model directory names that have sources.yaml."""
    return sorted(
        d.name
        for d in MODELS_DIR.iterdir()
        if d.is_dir() and d.name not in SKIP_DIRS and (d / "sources.yaml").exists()
    )


def _load_sources(model_slug: str) -> dict[str, Any]:
    """Load sources.yaml for a model. Raises typer.Exit on missing/malformed files."""
    path = MODELS_DIR / model_slug / "sources.yaml"
    if not path.exists():
        console.print(f"[red]Model '{model_slug}' not found in {MODELS_DIR}[/red]")
        raise typer.Exit(1)
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        console.print(f"[red]Malformed YAML in {model_slug}/sources.yaml: {e}[/red]")
        raise typer.Exit(1) from e


@kb_app.command(name="status")
def status_cmd(
    model: Optional[str] = typer.Argument(None, help="Specific model slug"),
) -> None:
    """Show knowledge base completion status for all models.

    Displays a matrix of which models have sources.yaml, docs, and R2 artifacts.

    Examples:
        bh kb status
        bh kb status esm2
    """
    slugs = [model] if model else _get_all_model_slugs()

    table = Table(title="Knowledge Base Status")
    table.add_column("Model", style="cyan", min_width=20)
    table.add_column("sources", justify="center")
    table.add_column("README", justify="center")
    table.add_column("MODEL", justify="center")
    table.add_column("BIOLOGY", justify="center")
    table.add_column("compare", justify="center")
    table.add_column("Papers", justify="center")
    table.add_column("Applied", justify="center")
    table.add_column("pdf_r2", justify="center")

    complete = 0
    for slug in slugs:
        model_dir = MODELS_DIR / slug
        has_sources = (model_dir / "sources.yaml").exists()
        has_readme = (model_dir / "README.md").exists()
        has_model = (model_dir / "MODEL.md").exists()
        has_biology = (model_dir / "BIOLOGY.md").exists()
        has_comparison = (model_dir / "comparison.yaml").exists()

        sources = _load_sources(slug) if has_sources else {}
        papers = sources.get("primary_papers", [])
        applied = sources.get("applied_literature", [])
        has_r2 = any(
            (p.get("pdf_r2") or "").startswith("knowledge-base/") for p in papers
        )

        ok = "[green]Y[/green]"
        no = "[red]N[/red]"

        all_complete = (
            has_sources and has_readme and has_model and has_biology and has_comparison
        )
        if all_complete:
            complete += 1

        table.add_row(
            slug,
            ok if has_sources else no,
            ok if has_readme else no,
            ok if has_model else no,
            ok if has_biology else no,
            ok if has_comparison else no,
            str(len(papers)),
            str(len(applied)),
            ok if has_r2 else no,
        )

    console.print(table)
    console.print(f"\n[bold]{complete}/{len(slugs)} models fully documented[/bold]")


@kb_app.command(name="validate")
def validate_cmd(  # noqa: C901
    model: Optional[str] = typer.Argument(None, help="Specific model to validate"),
) -> None:
    """Validate sources.yaml schema and documentation completeness.

    Checks for: required fields, valid enum values, type consistency,
    missing documentation files, R2 path formatting, and pending uploads.

    Examples:
        bh kb validate
        bh kb validate esm2
    """
    slugs = [model] if model else _get_all_model_slugs()
    total_errors = 0
    total_warnings = 0

    for slug in slugs:
        errors: list[str] = []
        warnings: list[str] = []
        model_dir = MODELS_DIR / slug

        # Check documentation files
        for doc in REQUIRED_DOCS:
            if not (model_dir / doc).exists():
                errors.append(f"Missing {doc}")

        # Validate sources.yaml
        sources_path = model_dir / "sources.yaml"
        if not sources_path.exists():
            errors.append("Missing sources.yaml")
            _print_validation_results(slug, errors, warnings)
            total_errors += len(errors)
            continue

        sources = _load_sources(slug)

        # Required top-level fields
        for field in REQUIRED_FIELDS:
            if field not in sources or not sources[field]:
                errors.append(f"Missing required field: {field}")

        # License validation
        lic = sources.get("license", {})
        if isinstance(lic, dict) and not lic.get("type"):
            errors.append("license.type is required")

        # molecule_types validation
        for mt in sources.get("molecule_types", []):
            if mt not in VALID_MOLECULE_TYPES:
                warnings.append(f"Unrecognized molecule_type: '{mt}'")

        # tasks validation
        for task in sources.get("tasks", []):
            if task not in VALID_TASKS:
                warnings.append(f"Unrecognized task: '{task}'")

        # Primary papers validation
        for i, paper in enumerate(sources.get("primary_papers", [])):
            for field in REQUIRED_PAPER_FIELDS:
                if field not in paper or not paper[field]:
                    errors.append(f"primary_papers[{i}] missing: {field}")

            # molecule_focus type check (should be string, not list)
            mf = paper.get("molecule_focus")
            if isinstance(mf, list):
                warnings.append(
                    f"primary_papers[{i}].molecule_focus is a list (should be string)"
                )

        # Applied literature validation
        for i, paper in enumerate(sources.get("applied_literature", [])):
            if not paper.get("title"):
                errors.append(f"applied_literature[{i}] missing: title")

            # molecule_focus type check
            mf = paper.get("molecule_focus")
            if isinstance(mf, list):
                warnings.append(
                    f"applied_literature[{i}].molecule_focus is a list (should be string)"
                )

        # Source repos validation
        for i, repo in enumerate(sources.get("source_repos", [])):
            rt = repo.get("type", "")
            if rt and rt not in VALID_REPO_TYPES:
                warnings.append(f"source_repos[{i}].type unrecognized: '{rt}'")
            if not repo.get("url"):
                errors.append(f"source_repos[{i}] missing: url")

        # Validate comparison.yaml
        comp_path = model_dir / "comparison.yaml"
        if not comp_path.exists():
            warnings.append("Missing comparison.yaml")
        else:
            try:
                with open(comp_path) as f:
                    comp = yaml.safe_load(f) or {}
                for section in ("strengths", "weaknesses", "use_when", "dont_use_when"):
                    count = len(comp.get(section) or [])
                    if count < 3:
                        errors.append(
                            f"comparison.yaml {section}: {count} entries (min 3)"
                        )
                    elif count < 5:
                        warnings.append(
                            f"comparison.yaml {section}: {count} entries (target 5+)"
                        )
                # Verify alternative/complement slugs exist
                all_slugs = {
                    d.name
                    for d in MODELS_DIR.iterdir()
                    if d.is_dir() and d.name not in SKIP_DIRS
                }
                for i, alt in enumerate(comp.get("alternatives") or []):
                    if not alt.get("model"):
                        warnings.append(
                            f"comparison.yaml alternatives[{i}] missing 'model' key"
                        )
                    elif alt["model"] not in all_slugs:
                        errors.append(
                            f"comparison.yaml alternative '{alt['model']}' not in models/"
                        )
                for i, compl in enumerate(comp.get("complements") or []):
                    if not compl.get("model"):
                        warnings.append(
                            f"comparison.yaml complements[{i}] missing 'model' key"
                        )
                    elif compl["model"] not in all_slugs:
                        errors.append(
                            f"comparison.yaml complement '{compl['model']}' not in models/"
                        )
            except yaml.YAMLError as e:
                errors.append(f"comparison.yaml malformed YAML: {e}")

        # Check for pending R2 uploads
        pending_primary = sum(
            1
            for p in sources.get("primary_papers", [])
            if not (p.get("pdf_r2") or "").startswith("knowledge-base/")
        )
        pending_applied = sum(
            1
            for p in sources.get("applied_literature", [])
            if not (p.get("pdf_r2") or "").startswith("knowledge-base/")
        )
        if pending_primary:
            warnings.append(f"{pending_primary} primary paper(s) missing from R2")
        if pending_applied:
            warnings.append(f"{pending_applied} applied paper(s) missing from R2")

        if errors or warnings:
            _print_validation_results(slug, errors, warnings)

        total_errors += len(errors)
        total_warnings += len(warnings)

    # Summary
    console.print(f"\n[bold]Validated {len(slugs)} models[/bold]")
    if total_errors:
        console.print(f"[red]{total_errors} errors[/red]")
    if total_warnings:
        console.print(f"[yellow]{total_warnings} warnings[/yellow]")
    if not total_errors and not total_warnings:
        console.print("[green]All models pass validation![/green]")

    if total_errors:
        raise typer.Exit(1)


def _print_validation_results(
    slug: str, errors: list[str], warnings: list[str]
) -> None:
    """Print validation results for a single model."""
    if errors:
        console.print(f"\n[red bold]{slug}[/red bold]")
        for e in errors:
            console.print(f"  [red]ERROR: {e}[/red]")
    if warnings:
        if not errors:
            console.print(f"\n[yellow bold]{slug}[/yellow bold]")
        for w in warnings:
            console.print(f"  [yellow]WARN: {w}[/yellow]")


@kb_app.command(name="sources")
def sources_cmd(
    model: str = typer.Argument(..., help="Model slug"),
) -> None:
    """Display sources.yaml summary for a model.

    Examples:
        bh kb sources esm2
        bh kb sources boltz
    """
    sources = _load_sources(model)

    console.print(f"\n[bold cyan]{sources.get('display_name', model)}[/bold cyan]")
    console.print(f"Slug: {sources.get('model_slug', '?')}")

    lic = sources.get("license", {})
    if isinstance(lic, dict):
        console.print(f"License: {lic.get('type', '?')}")
    console.print(f"Molecules: {', '.join(sources.get('molecule_types', []))}")
    console.print(f"Tasks: {', '.join(sources.get('tasks', []))}")

    # Primary papers
    papers = sources.get("primary_papers", [])
    console.print(f"\n[bold]Primary Papers ({len(papers)})[/bold]")
    for p in papers:
        r2 = p.get("pdf_r2") or ""
        r2_status = (
            "[green]R2[/green]"
            if r2.startswith("knowledge-base/")
            else "[red]no R2[/red]"
        )
        console.print(f"  - {p.get('title', '?')} ({p.get('year', '?')}) {r2_status}")

    # Applied literature
    applied = sources.get("applied_literature", [])
    console.print(f"\n[bold]Applied Literature ({len(applied)})[/bold]")
    for a in applied:
        console.print(f"  - {a.get('title', '?')} ({a.get('year', '?')})")

    # Source repos
    repos = sources.get("source_repos", [])
    console.print(f"\n[bold]Source Repos ({len(repos)})[/bold]")
    for r in repos:
        console.print(f"  - [{r.get('type', '?')}] {r.get('url', '?')}")
