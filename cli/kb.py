"""
Knowledge Base CLI commands.

Provides tools for inspecting, validating, and managing the model knowledge base.
"""

import datetime
from pathlib import Path
from typing import Optional

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


def _load_sources(model_slug: str) -> dict:
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
        bm kb status
        bm kb status esm2
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
        bm kb validate
        bm kb validate esm2
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


@kb_app.command(name="matrix")
def matrix_cmd(
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path (default: MODEL_COMPARISON_MATRIX.md at repo root)",
    ),
) -> None:
    """Generate the MODEL_COMPARISON_MATRIX.md comparison document.

    Reads all models/*/comparison.yaml and sources.yaml files and produces a
    comprehensive markdown document with overview tables, molecule-type groupings,
    decision trees, alternatives/complements matrices, and protocol coverage.

    Examples:
        bm kb matrix
        bm kb matrix --output docs/comparison.md
    """
    from models.scripts.generate_comparison_matrix import main as generate_main

    argv: list[str] = []
    if output:
        argv.extend(["--output", output])
    generate_main(argv)
    console.print("[green]Comparison matrix generated successfully.[/green]")


def _collect_missing_papers(
    slugs: list[str],
) -> tuple[
    list[tuple[str, dict, str]],
    list[tuple[str, dict, str]],
    list[tuple[str, dict, str]],
]:
    """Scan sources.yaml files and categorize papers missing from R2."""
    open_access: list[tuple[str, dict, str]] = []
    paywall: list[tuple[str, dict, str]] = []
    no_paper: list[tuple[str, dict, str]] = []

    for slug in slugs:
        model_dir = MODELS_DIR / slug
        if not (model_dir / "sources.yaml").exists():
            continue
        sources = _load_sources(slug)
        for section in ("primary_papers", "applied_literature"):
            for paper in sources.get(section, []):
                pdf_r2 = paper.get("pdf_r2") or ""
                if (
                    pdf_r2
                    and pdf_r2 != "pending"
                    and pdf_r2.startswith("knowledge-base/")
                ):
                    continue

                doi = paper.get("doi", "")
                arxiv = paper.get("arxiv", "")
                kind = "primary" if section == "primary_papers" else "applied"

                # Categorize: no identifiers = no paper, arxiv/biorxiv = open access.
                # bioRxiv/medRxiv DOIs use the 10.1101/ prefix (e.g. 10.1101/2024.11.19.624167).
                if not doi and not arxiv:
                    no_paper.append((slug, paper, kind))
                elif arxiv or "10.1101/" in doi or "biorxiv" in doi.lower():
                    open_access.append((slug, paper, kind))
                else:
                    paywall.append((slug, paper, kind))

    return open_access, paywall, no_paper


def _format_missing_report(
    open_access: list[tuple[str, dict, str]],
    paywall: list[tuple[str, dict, str]],
    no_paper: list[tuple[str, dict, str]],
) -> str:
    """Format missing papers into a markdown report."""

    lines = [
        "# Missing R2 Papers Report",
        "",
        f"Generated: {datetime.date.today().isoformat()}",
        f"Total missing: {len(open_access) + len(paywall) + len(no_paper)} papers",
        "",
    ]

    if open_access:
        lines.append(f"## Open Access -- Actionable ({len(open_access)} papers)")
        lines.append("")
        lines.append("| Model | Type | Title | DOI/arXiv | Action |")
        lines.append("|---|---|---|---|---|")
        for slug, p, kind in open_access:
            doi = p.get("doi", p.get("arxiv", ""))
            lines.append(
                f"| {slug} | {kind} | {p.get('title', '?')[:60]} | {doi} | "
                f"Download PDF and run `kb_acquire.py --models {slug}` |"
            )
        lines.append("")

    if paywall:
        lines.append(f"## Paywall -- Requires Access ({len(paywall)} papers)")
        lines.append("")
        lines.append("| Model | Type | Title | DOI | Strategy |")
        lines.append("|---|---|---|---|---|")
        for slug, p, kind in paywall:
            doi = p.get("doi", "")
            lines.append(
                f"| {slug} | {kind} | {p.get('title', '?')[:60]} | {doi} | "
                "Institutional access, SharedIt link, or author request |"
            )
        lines.append("")

    if no_paper:
        lines.append(f"## No Paper / Non-Academic ({len(no_paper)} entries)")
        lines.append("")
        for slug, p, kind in no_paper:
            lines.append(
                f"- **{slug}** ({kind}): {p.get('title', 'No published paper')}"
            )
        lines.append("")

    if not open_access and not paywall and not no_paper:
        lines.append("**All papers are in R2!**")

    return "\n".join(lines)


@kb_app.command(name="missing")
def missing_cmd(
    model: Optional[str] = typer.Argument(None, help="Specific model slug"),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Write report to file instead of stdout"
    ),
) -> None:
    """Report papers with pending R2 uploads.

    Scans sources.yaml files for primary and applied papers where pdf_r2
    is empty, "pending", or missing. Groups by acquisition difficulty.

    Examples:
        bm kb missing
        bm kb missing esm2
        bm kb missing --output models/scripts/MISSING_R2_PAPERS.md
    """
    slugs = [model] if model else _get_all_model_slugs()
    open_access, paywall, no_paper = _collect_missing_papers(slugs)
    report = _format_missing_report(open_access, paywall, no_paper)

    if output:
        Path(output).write_text(report)
        console.print(f"[green]Report written to {output}[/green]")
    else:
        console.print(report)


@kb_app.command(name="sources")
def sources_cmd(
    model: str = typer.Argument(..., help="Model slug"),
) -> None:
    """Display sources.yaml summary for a model.

    Examples:
        bm kb sources esm2
        bm kb sources boltz
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
