import os
import subprocess
import sys
from collections import Counter
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Annotated, NoReturn, Optional, cast

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from models.commons.core.logging import get_logger
from models.commons.model.config import ModelFamily, ResolvedVariant
from models.commons.model.naming import model_app_path, slug_to_module
from models.commons.model.schema import ModalResourceSpec

"""
Unified deployment script for biolm-hub models.

This script handles single-variant, multi-variant, and whole-catalog
deployments by leveraging the ModelFamily configuration defined in each model's
config.py.

Usage via bh CLI:
    # Deploy a model's default variant (the first-declared; smallest for most families)
    bh deploy esm2

    # Deploy every variant of the family
    bh deploy esm2 --all-variants

    # Deploy a specific variant
    bh deploy esm2 --variant MODEL_SIZE=150m

    # Deploy multiple models (default variant each)
    bh deploy esm2 esmc esmfold --force

    # Deploy the DEFAULT variant of every model in the catalog
    bh deploy --all

    # Deploy EVERY variant of every model
    bh deploy --all --all-variants

Credentials: if the Modal workspace has no `cloudflare-r2` secret, the deploy
auto-switches to credential-less mode (public weights read over HTTP, no
self-population). Set BIOLM_SKIP_MODAL_SECRETS explicitly to override the
auto-detection in either direction.
"""

console = Console()
logger = get_logger(__name__)

# Default bounded parallelism for ``bh deploy --all``.
DEFAULT_MAX_CONCURRENCY = 4

# The exact command that deploys every variant of every model — quoted verbatim
# in the "default variants only" notice so a user is never misled.
ALL_VARIANTS_COMMAND = "bh deploy --all --all-variants"


@dataclass(frozen=True)
class PlannedVariant:
    """One (model, variant) pair selected for deployment."""

    model_name: str
    variant: ResolvedVariant


@dataclass
class DeployOutcome:
    """The result of attempting to deploy one planned variant."""

    planned: PlannedVariant
    status: str  # "deployed" | "failed"
    detail: str = ""


def _run_forced_deploy(
    model_name: str, variant_env_vars: dict[str, str]
) -> tuple[bool, str, str]:
    """Run one **non-interactive** (forced) variant deploy in a clean subprocess.

    This is the single source of truth for the forced deploy invocation: it runs
    ``python models/<name>/app.py --force-deploy`` with stdin routed to
    ``/dev/null`` so Modal's per-deploy "Continue?" gate can never block on EOF,
    and captures output so callers can report a concise failure reason.

    Returns ``(success, captured_output, failure_detail)`` where ``failure_detail``
    is a one-line reason on failure (empty on success).
    """
    model_path = model_app_path(model_name)
    env = os.environ.copy()
    env.update(variant_env_vars)
    cmd = [sys.executable, str(model_path), "--force-deploy"]

    try:
        result = subprocess.run(
            cmd,
            env=env,
            check=True,
            stdin=subprocess.DEVNULL,  # Prevent any interactive input prompts
            capture_output=True,
            text=True,
        )
        output = result.stdout + (f"\n{result.stderr}" if result.stderr else "")
        return True, output, ""
    except subprocess.CalledProcessError as e:
        output = (e.stdout or "") + (f"\n{e.stderr}" if e.stderr else "")
        detail = _first_error_line(e.stderr or e.stdout or "") or (
            f"exited with code {e.returncode}"
        )
        return False, output, detail
    except OSError as e:
        return False, "", str(e)


def _first_error_line(output: str) -> str:
    """Best-effort one-line failure reason: the last non-empty line of output."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines[-1][:200] if lines else ""


def deploy_single_variant(
    model_name: str, variant_env_vars: dict[str, str], force: bool = False
) -> bool:
    """Deploy a single model variant using subprocess to ensure clean environment."""
    model_path = model_app_path(model_name)

    if force:
        print("  🚀 Force deployment enabled (--force flag active)")

    # Format and display the command being executed
    cmd = [sys.executable, str(model_path)]
    if force:
        cmd.append("--force-deploy")
    if variant_env_vars:
        env_str = " ".join(f"{k}={v}" for k, v in variant_env_vars.items())
        print(f"  Executing: {env_str} {' '.join(cmd)}")
    else:
        print(f"  Executing: {' '.join(cmd)}")

    # Stream the build output live in both cases. When force=True, route stdin to
    # /dev/null so Modal's per-deploy "Continue?" gate can't block on EOF; otherwise
    # leave stdin attached so an interactive confirmation still works. (The capturing
    # _run_forced_deploy is reserved for the parallel `--all` path, where interleaved
    # live output would be unreadable.)
    env = os.environ.copy()
    env.update(variant_env_vars)
    stdin = subprocess.DEVNULL if force else None
    try:
        subprocess.run(cmd, env=env, check=True, stdin=stdin)
        return True
    except subprocess.CalledProcessError:
        return False


def get_model_family(model_name: str) -> Optional[ModelFamily]:
    """Load the ModelFamily from a model's config.py."""
    try:
        # Accept either a slug (hyphen) or a directory name; naming normalizes both.
        config_module = import_module(f"{slug_to_module(model_name)}.config")

        if not hasattr(config_module, "MODEL_FAMILY"):
            print(
                f"❌ ERROR: models/{model_name}/config.py does not define MODEL_FAMILY"
            )
            return None

        return cast(ModelFamily, config_module.MODEL_FAMILY)
    except ImportError as e:
        print(f"❌ ERROR: Could not import models/{model_name}/config.py: {e}")
        return None


def parse_variant_spec(variant_spec: str) -> dict[str, str]:
    """Parse variant specification like 'MODEL_SIZE=150m,MODEL_ACTION=encode'."""
    if not variant_spec:
        return {}

    variant_dict: dict[str, str] = {}
    for pair in variant_spec.split(","):
        if "=" not in pair:
            print(f"❌ ERROR: Invalid variant spec format: {pair}")
            print("Expected format: KEY=value or KEY1=value1,KEY2=value2")
            sys.exit(1)
        key, value = pair.split("=", 1)
        variant_dict[key.strip()] = value.strip()

    return variant_dict


def _get_variants_to_deploy(
    model_family: ModelFamily, variant_spec: Optional[str], all_variants: bool
) -> list[ResolvedVariant]:
    """Select which variants to deploy.

    A specific ``--variant`` wins; otherwise ``--all-variants`` deploys the whole
    family and the default (no flag) deploys a single variant — the first-declared,
    which is the smallest/base for most families. This keeps ``bh deploy <model>``
    a fast, cheap, single-endpoint operation.
    """
    if variant_spec:
        # Deploy specific variant
        variant_dict = parse_variant_spec(variant_spec)
        try:
            variant = model_family.find_variant(**variant_dict)
            print(f"Deploying specific variant: {variant.modal_app_name}")
            return [variant]
        except ValueError as e:
            print(f"❌ ERROR: {e}")
            sys.exit(1)

    all_resolved = model_family.resolved_variants

    if all_variants:
        if len(all_resolved) > 1:
            print(f"Deploying all {len(all_resolved)} variants")
        return all_resolved

    # Default: a single variant so no flag is needed for the common case.
    default_variant = all_resolved[0]
    if len(all_resolved) > 1:
        print(
            f"Deploying default variant: {default_variant.modal_app_name} "
            f"(1 of {len(all_resolved)} — use --all-variants for the whole family, "
            f"or --variant KEY=value to pick another)"
        )
    return [default_variant]


def _deploy_variants(
    model_name: str, variants_to_deploy: list[ResolvedVariant], force: bool
) -> list[str]:
    """Deploy a list of variants and track failures."""
    failed_deployments: list[str] = []

    for i, variant in enumerate(variants_to_deploy, 1):
        if len(variants_to_deploy) > 1:
            print(
                f"\n[{i}/{len(variants_to_deploy)}] Deploying: {variant.modal_app_name}"
            )
        else:
            print(f"\nDeploying: {variant.modal_app_name}")

        if variant.env_vars:
            print(f"  Environment: {variant.env_vars}")

        # Deploy this variant
        success = deploy_single_variant(model_name, variant.env_vars, force=force)

        if success:
            print(f"✅ Successfully deployed {variant.modal_app_name}")
        else:
            failed_deployments.append(variant.modal_app_name)
            print(f"❌ Failed to deploy {variant.modal_app_name}")
            if not force and len(variants_to_deploy) > 1:
                response = input("Continue with remaining variants? [y/N] ")
                if response.lower() != "y":
                    break

    return failed_deployments


def _print_deployment_summary(
    model_name: str,
    variants_to_deploy: list[ResolvedVariant],
    failed_deployments: list[str],
) -> None:
    """Print the deployment summary."""
    if failed_deployments:
        print("\n⚠️  Deployment completed with failures:")
        for failed in failed_deployments:
            print(f"   ❌ {failed}")
        sys.exit(1)
    else:
        total = len(variants_to_deploy)
        if total == 1:
            print(f"\n✅ Successfully deployed {model_name}")
        else:
            print(f"\n✅ Successfully deployed all {total} variants of {model_name}")


def deploy_model(
    model_name: str,
    force: bool = False,
    variant_spec: Optional[str] = None,
    all_variants: bool = False,
) -> None:
    """
    Deploy a model: its default variant, all variants, or a specific one.

    Args:
        model_name: Name of the model directory (e.g., "esm2", "esmfold")
        force: Whether to force deployment without prompts
        variant_spec: Optional specific variant to deploy (e.g., "MODEL_SIZE=150m")
        all_variants: Deploy every variant instead of just the default
    """
    # Handle special case where model_name is "." (current directory)
    if model_name == ".":
        model_name = Path.cwd().name
        print(f"📁 Deploying model from current directory: {model_name}")

    print(f"\n🚀 Deploying Model: {model_name}")

    # Load the model family configuration
    model_family = get_model_family(model_name)
    if not model_family:
        sys.exit(1)

    # Get variants to deploy
    variants_to_deploy = _get_variants_to_deploy(
        model_family, variant_spec, all_variants
    )

    # Deploy each variant
    failed_deployments = _deploy_variants(model_name, variants_to_deploy, force)

    # Print summary
    _print_deployment_summary(model_name, variants_to_deploy, failed_deployments)


def _maybe_enable_credential_less() -> None:
    """Auto-enable credential-less mode when the workspace lacks the R2 secret.

    Probes the Modal workspace for the ``cloudflare-r2`` secret. This lives in the
    CLI — which is authenticated — precisely because it must NOT run at ``app.py``
    import time (importing a model must stay auth-free so CI, unit tests, and docs
    generation work with no Modal token). If the secret is absent, set
    ``BIOLM_SKIP_MODAL_SECRETS`` for the deploy subprocess so ``bh deploy <model>``
    works out-of-the-box against the public bucket over HTTP — no flag required. An
    explicit ``BIOLM_SKIP_MODAL_SECRETS`` (either value) always wins, and a probe that
    can't reach Modal changes nothing (the deploy then surfaces its own auth error).
    """
    if "BIOLM_SKIP_MODAL_SECRETS" in os.environ:
        return  # explicit override wins, in both directions

    import modal
    from modal.exception import NotFoundError

    from models.commons.util.config import cloudflare_r2_secret_name

    try:
        modal.Secret.from_name(cloudflare_r2_secret_name).hydrate()
        return  # secret present → maintainer mode (self-populate), unchanged
    except NotFoundError:
        os.environ["BIOLM_SKIP_MODAL_SECRETS"] = "1"
        console.print(
            f"[yellow]No '{cloudflare_r2_secret_name}' secret in this Modal "
            "workspace — deploying credential-less: public weights are read "
            "anonymously over HTTP (no self-population). Provision the secret "
            "or run `bh setup` to self-populate your own bucket.[/yellow]"
        )
    except Exception:
        return  # inconclusive probe (no auth / network) → leave behavior unchanged


def _apply_cache_env(cache: Optional[bool]) -> None:
    """Bake the response-cache toggle into the deploy subprocess environment.

    ``None`` (no flag) leaves any pre-existing export untouched; ``--cache`` forces
    it on, ``--no-cache`` forces it off. Read inside the container via
    ``BIOLM_CACHE_ENABLED``; the deploy subprocess inherits ``os.environ``.
    """
    if cache is True:
        os.environ["BIOLM_CACHE_ENABLED"] = "1"
    elif cache is False:
        os.environ.pop("BIOLM_CACHE_ENABLED", None)


# ---------------------------------------------------------------------------
# Catalog-wide deploy (`bh deploy --all`)
# ---------------------------------------------------------------------------


def _abort(message: str) -> NoReturn:
    """Print a CLI error and exit non-zero."""
    console.print(f"[red]✗ {message}[/red]")
    raise typer.Exit(1)


def _accelerator_label(spec: ModalResourceSpec) -> str:
    """Human-readable accelerator for a variant (``"CPU"`` when none).

    Mirrors the label the catalog/docs use, with a compact ``×N`` suffix for
    multi-GPU variants so it also serves as a stable grouping key.
    """
    if spec.gpu is None:
        return "CPU"
    label = str(spec.gpu.value).upper()
    if spec.gpu_count and spec.gpu_count > 1:
        return f"{label}×{spec.gpu_count}"
    return label


def _discover_model_names() -> list[str]:
    """Every deployable model directory name (skips ``commons``/``dummy``).

    Reuses the same discovery the GitHub catalog + docs generation use, so
    ``--all`` sees exactly the deployable set — no separate list to keep in sync.
    """
    from tooling.gen_model_catalog import discover_models

    return discover_models()


def _parse_slug_csv(value: Optional[str]) -> list[str]:
    """Parse a comma-separated model-slug list; empty/whitespace entries dropped."""
    if not value:
        return []
    return [slug.strip() for slug in value.split(",") if slug.strip()]


def _load_selected_families(
    only: Optional[str], exclude: Optional[str]
) -> list[tuple[str, ModelFamily]]:
    """Resolve the ``--only``/``--exclude`` filters to concrete model families.

    Validates every supplied slug against the discovered set (erroring on unknown
    names) and returns ``(model_name, family)`` pairs in catalog order.
    """
    known = _discover_model_names()
    only_slugs = _parse_slug_csv(only)
    exclude_slugs = _parse_slug_csv(exclude)

    unknown = sorted({*only_slugs, *exclude_slugs} - set(known))
    if unknown:
        _abort(
            f"Unknown model slug(s): {', '.join(unknown)}.\n"
            f"Known models: {', '.join(known)}"
        )

    selected = [
        name
        for name in known
        if (not only_slugs or name in only_slugs) and name not in exclude_slugs
    ]

    families: list[tuple[str, ModelFamily]] = []
    for name in selected:
        family = get_model_family(name)
        if family is None:
            _abort(f"Could not load config for model '{name}'.")
        families.append((name, family))
    return families


def _build_plan(
    families: list[tuple[str, ModelFamily]],
    *,
    all_variants: bool,
    cpu_only: bool,
) -> list[PlannedVariant]:
    """Expand selected families into the concrete list of variants to deploy.

    Default: the single default (first-declared, cheapest) variant per model.
    ``all_variants``: every variant. ``cpu_only`` drops any GPU-backed variant
    from whatever set was selected.
    """
    plan: list[PlannedVariant] = []
    for name, family in families:
        variants = (
            family.resolved_variants if all_variants else family.resolved_variants[:1]
        )
        for variant in variants:
            if cpu_only and variant.modal_resource_spec.gpu is not None:
                continue
            plan.append(PlannedVariant(model_name=name, variant=variant))
    return plan


def _apply_skip_deployed(
    plan: list[PlannedVariant], skip_deployed: bool, environment: Optional[str]
) -> tuple[list[PlannedVariant], list[PlannedVariant]]:
    """Partition the plan into (to_deploy, already_deployed) when ``--skip-deployed``.

    Reuses the catalog's Modal query. If the query can't run, nothing is skipped.
    """
    if not skip_deployed:
        return plan, []

    from gateway.catalog.deployment_status import get_deployed_app_names

    deployed = get_deployed_app_names(environment)
    if deployed is None:
        console.print(
            "[yellow]Could not query deployed Modal apps; "
            "--skip-deployed has no effect.[/yellow]"
        )
        return plan, []

    to_deploy = [p for p in plan if p.variant.modal_app_name not in deployed]
    skipped = [p for p in plan if p.variant.modal_app_name in deployed]
    return to_deploy, skipped


def _gpu_breakdown(plan: list[PlannedVariant]) -> str:
    """CPU-vs-GPU-by-tier summary, e.g. ``"32 CPU, 6 GPU: 4×T4, 1×L40S, 1×A100"``."""
    labels = [_accelerator_label(p.variant.modal_resource_spec) for p in plan]
    gpu_labels = [label for label in labels if label != "CPU"]
    cpu_count = len(labels) - len(gpu_labels)

    line = f"{cpu_count} CPU, {len(gpu_labels)} GPU"
    if gpu_labels:
        counts = Counter(gpu_labels)
        detail = ", ".join(f"{n}×{label}" for label, n in sorted(counts.items()))
        line = f"{line}: {detail}"
    return line


def _variant_scope_notice(all_variants: bool, *, after: bool) -> Panel:
    """The impossible-to-miss notice about which variants (default vs all) deploy."""
    if all_variants:
        verb = "were deployed" if after else "will be deployed"
        body = f"ALL variants of every model {verb}."
        return Panel(body, title="ALL VARIANTS", border_style="cyan", expand=False)

    tense = "was deployed" if after else "will be deployed"
    body = (
        f"ONLY the DEFAULT (cheapest) variant of each model {tense} — "
        "NOT every variant.\n"
        "To deploy every variant of every model, run:\n\n"
        f"    {ALL_VARIANTS_COMMAND}"
    )
    return Panel(
        body,
        title="⚠  DEFAULT VARIANTS ONLY",
        border_style="yellow",
        expand=False,
    )


def _print_preflight_summary(
    to_deploy: list[PlannedVariant], skipped: list[PlannedVariant]
) -> None:
    """Print the pre-deploy counts + CPU/GPU breakdown."""
    n_models = len({p.model_name for p in to_deploy})
    console.print(
        f"[bold]Deploying {len(to_deploy)} variant(s) "
        f"across {n_models} model(s).[/bold]"
    )
    console.print(f"  Resources: {_gpu_breakdown(to_deploy)}")
    if skipped:
        console.print(
            f"  [dim]Skipping {len(skipped)} already-deployed variant(s).[/dim]"
        )


def _print_plan(to_deploy: list[PlannedVariant], skipped: list[PlannedVariant]) -> None:
    """Print the full model → variant → GPU plan (used by ``--dry-run``)."""
    table = Table(title="Deployment plan", header_style="bold")
    table.add_column("Model", style="cyan")
    table.add_column("Variant (Modal app)")
    table.add_column("Accelerator")
    table.add_column("Action")
    for p in to_deploy:
        table.add_row(
            p.model_name,
            p.variant.modal_app_name,
            _accelerator_label(p.variant.modal_resource_spec),
            "deploy",
        )
    for p in skipped:
        table.add_row(
            p.model_name,
            p.variant.modal_app_name,
            _accelerator_label(p.variant.modal_resource_spec),
            "skip (deployed)",
        )
    console.print(table)


def _execute_plan(
    to_deploy: list[PlannedVariant], max_concurrency: int
) -> list[DeployOutcome]:
    """Deploy every planned variant with bounded parallelism, continue-on-error.

    Each sub-deploy runs the shared non-interactive (forced) path so Modal's
    per-deploy prompt can never block; one failure never aborts the rest.
    """
    workers = max(1, min(max_concurrency, len(to_deploy)))
    logger.info(
        "Deploying %d variant(s) with max concurrency %d", len(to_deploy), workers
    )

    outcomes: list[DeployOutcome] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures: dict[Future[tuple[bool, str, str]], PlannedVariant] = {
            pool.submit(_run_forced_deploy, p.model_name, p.variant.env_vars): p
            for p in to_deploy
        }
        for future in as_completed(futures):
            planned = futures[future]
            app_name = planned.variant.modal_app_name
            try:
                success, _output, detail = future.result()
            except Exception as exc:  # defensive: unexpected runner failure
                success, detail = False, str(exc)

            if success:
                console.print(f"[green]✓[/green] deployed {app_name}")
                outcomes.append(DeployOutcome(planned=planned, status="deployed"))
            else:
                console.print(f"[red]✗[/red] failed {app_name}: {detail}")
                logger.error("Deploy failed for %s: %s", app_name, detail)
                outcomes.append(
                    DeployOutcome(planned=planned, status="failed", detail=detail)
                )
    return outcomes


def _print_final_summary(
    outcomes: list[DeployOutcome],
    skipped: list[PlannedVariant],
    all_variants: bool,
) -> None:
    """Print the ✓/✗/⤼ results table, counts, and the closing variant notice."""
    deployed = [o for o in outcomes if o.status == "deployed"]
    failed = [o for o in outcomes if o.status == "failed"]

    table = Table(title="Deployment summary", header_style="bold")
    table.add_column("Result")
    table.add_column("Model", style="cyan")
    table.add_column("Variant (Modal app)")
    table.add_column("Detail")
    for o in deployed:
        table.add_row(
            "[green]✓ deployed[/green]",
            o.planned.model_name,
            o.planned.variant.modal_app_name,
            "",
        )
    for o in failed:
        table.add_row(
            "[red]✗ failed[/red]",
            o.planned.model_name,
            o.planned.variant.modal_app_name,
            o.detail,
        )
    for p in skipped:
        table.add_row(
            "[dim]⤼ skipped[/dim]",
            p.model_name,
            p.variant.modal_app_name,
            "already deployed",
        )
    console.print(table)
    console.print(
        f"[bold]{len(deployed)} deployed, {len(failed)} failed, "
        f"{len(skipped)} skipped.[/bold]"
    )
    console.print(_variant_scope_notice(all_variants, after=True))


def deploy_all(
    *,
    all_variants: bool,
    cpu_only: bool,
    only: Optional[str],
    exclude: Optional[str],
    skip_deployed: bool,
    dry_run: bool,
    yes: bool,
    max_concurrency: int,
    environment: Optional[str],
) -> None:
    """Deploy the default (or, with ``all_variants``, every) variant of every model."""
    families = _load_selected_families(only, exclude)
    plan = _build_plan(families, all_variants=all_variants, cpu_only=cpu_only)
    if not plan:
        console.print(
            "[yellow]No models match the given filters — nothing to deploy.[/yellow]"
        )
        return

    to_deploy, skipped = _apply_skip_deployed(plan, skip_deployed, environment)

    # (a) Prominent up-front notice + preflight summary, BEFORE deploying.
    _print_preflight_summary(to_deploy, skipped)
    console.print(_variant_scope_notice(all_variants, after=False))

    if dry_run:
        _print_plan(to_deploy, skipped)
        # Repeat the notice at the end of the plan so it can't be missed.
        console.print(_variant_scope_notice(all_variants, after=False))
        return

    if not to_deploy:
        console.print(
            "[yellow]All matching variants are already deployed — "
            "nothing to do.[/yellow]"
        )
        return

    if not yes and not typer.confirm("Continue?"):
        console.print("Aborted — nothing was deployed.")
        raise typer.Exit(1)

    # Probe for credential-less mode once, before spawning any deploy subprocess.
    _maybe_enable_credential_less()

    outcomes = _execute_plan(to_deploy, max_concurrency)

    # (b) Final summary, ending again with the default-variants-only notice.
    _print_final_summary(outcomes, skipped, all_variants)

    if any(o.status == "failed" for o in outcomes):
        raise typer.Exit(1)


def _validate_deploy_args(
    *,
    models: Optional[list[str]],
    all_models: bool,
    variant: Optional[str],
    only: Optional[str],
    exclude: Optional[str],
    cpu_only: bool,
    skip_deployed: bool,
    dry_run: bool,
    yes: bool,
) -> None:
    """Validate flag combinations for ``bh deploy`` and error clearly on misuse."""
    if all_models and models:
        _abort(
            "Cannot combine --all with a positional MODEL argument. "
            "Use `bh deploy <model>` OR `bh deploy --all`."
        )
    if not all_models and not models:
        _abort("Provide at least one MODEL to deploy, or --all for the whole catalog.")
    if all_models and variant:
        _abort("--variant targets a single model and cannot be combined with --all.")

    if not all_models:
        batch_only = {
            "--only": bool(only),
            "--exclude": bool(exclude),
            "--cpu-only": cpu_only,
            "--skip-deployed": skip_deployed,
            "--dry-run": dry_run,
            "--yes/-y": yes,
        }
        offenders = [flag for flag, used in batch_only.items() if used]
        if offenders:
            verb = "applies" if len(offenders) == 1 else "apply"
            _abort(f"{', '.join(offenders)} only {verb} with --all.")


# Main deploy command function
def deploy_cmd(
    models: Annotated[
        Optional[list[str]],
        typer.Argument(
            help="Model(s) to deploy (e.g., esm2 esmc esmfold). Omit with --all."
        ),
    ] = None,
    all_models: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Deploy every model in the catalog. Deploys each model's DEFAULT "
            "(cheapest) variant; add --all-variants for every variant.",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Force deployment without confirmation prompts",
        ),
    ] = False,
    all_variants: Annotated[
        bool,
        typer.Option(
            "--all-variants",
            help="Deploy every variant (of the family, or with --all, of every "
            "model) instead of just the default/first variant.",
        ),
    ] = False,
    force_deploy: Annotated[
        bool,
        typer.Option(
            "--force-deploy",
            help="Force deployment without confirmation prompts (alias)",
            hidden=True,
        ),
    ] = False,
    variant: Annotated[
        Optional[str],
        typer.Option(
            "--variant",
            help="Deploy specific variant (e.g., MODEL_SIZE=150m)",
        ),
    ] = None,
    cache: Annotated[
        Optional[bool],
        typer.Option(
            "--cache/--no-cache",
            help="Bake response caching (BIOLM_CACHE_ENABLED) into the "
            "deployment. Off by default.",
        ),
    ] = None,
    cpu_only: Annotated[
        bool,
        typer.Option(
            "--cpu-only",
            help="With --all: only deploy models whose selected variant runs on CPU.",
        ),
    ] = False,
    only: Annotated[
        Optional[str],
        typer.Option(
            "--only",
            help="With --all: comma-separated model slugs to include "
            "(e.g. esm2,esmc).",
        ),
    ] = None,
    exclude: Annotated[
        Optional[str],
        typer.Option(
            "--exclude",
            help="With --all: comma-separated model slugs to skip.",
        ),
    ] = None,
    skip_deployed: Annotated[
        bool,
        typer.Option(
            "--skip-deployed",
            help="With --all: query Modal and skip apps that are already deployed.",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="With --all: print the full deploy plan and exit without "
            "deploying or prompting.",
        ),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="With --all: skip the top-level confirmation prompt.",
        ),
    ] = False,
    max_concurrency: Annotated[
        int,
        typer.Option(
            "--max-concurrency",
            min=1,
            help="With --all: max models to deploy in parallel (default 4).",
        ),
    ] = DEFAULT_MAX_CONCURRENCY,
    environment: Annotated[
        Optional[str],
        typer.Option(
            "--env",
            "-e",
            help="Modal environment to target (defaults to your active profile).",
        ),
    ] = None,
) -> None:
    """
    Deploy one or more biolm-hub models, or the whole catalog with --all.

    By default deploys each named model's single default variant; pass
    --all-variants for the whole family or --variant KEY=value for a specific one.
    Use --all to deploy every model in the catalog (default variant each; add
    --all-variants for every variant). If the Modal workspace has no cloudflare-r2
    secret, the deploy auto-switches to credential-less mode (public weights over
    HTTP).

    Examples:
        bh deploy esm2
        bh deploy esm2 --all-variants
        bh deploy esm2 --variant MODEL_SIZE=150m
        bh deploy esm2 --cache          # enable response caching for this deploy
        bh deploy esm2 esmc esmfold --force
        bh deploy --all                 # default variant of every model
        bh deploy --all --all-variants  # EVERY variant of every model
        bh deploy --all --dry-run       # preview the plan, deploy nothing
        bh deploy --all --cpu-only --skip-deployed -y
    """

    # Consolidate force flags
    force = force or force_deploy

    _validate_deploy_args(
        models=models,
        all_models=all_models,
        variant=variant,
        only=only,
        exclude=exclude,
        cpu_only=cpu_only,
        skip_deployed=skip_deployed,
        dry_run=dry_run,
        yes=yes,
    )

    # Target a specific Modal environment for both the deployed-app query and the
    # deploy subprocesses (Modal reads MODAL_ENVIRONMENT), matching `bh serve`.
    if environment:
        os.environ["MODAL_ENVIRONMENT"] = environment

    # Catalog-wide path.
    if all_models:
        if not dry_run:
            _apply_cache_env(cache)
        deploy_all(
            all_variants=all_variants,
            cpu_only=cpu_only,
            only=only,
            exclude=exclude,
            skip_deployed=skip_deployed,
            dry_run=dry_run,
            yes=yes,
            max_concurrency=max_concurrency,
            environment=environment,
        )
        return

    # Single/multi-model path.
    #
    # Auto-detect credential-less mode (no cloudflare-r2 secret) once per
    # invocation, before spawning any deploy subprocess. Must run here
    # (authenticated CLI), not at app.py import time.
    _maybe_enable_credential_less()
    _apply_cache_env(cache)

    # Deploy each model
    for model_name in models or []:
        try:
            deploy_model(
                model_name=model_name,
                force=force,
                variant_spec=variant,
                all_variants=all_variants,
            )
        except SystemExit as e:
            if e.code != 0:
                console.print(f"[red]❌ Deployment for {model_name} failed![/red]")
                sys.exit(1)
        except Exception as e:
            console.print(f"[red]❌ Error deploying {model_name}: {e}[/red]")
            sys.exit(1)
