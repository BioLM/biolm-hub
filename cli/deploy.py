import os
import subprocess
import sys
from importlib import import_module
from pathlib import Path
from typing import Annotated, Optional, cast

import typer
from rich.console import Console

from models.commons.model.config import ModelFamily, ResolvedVariant

"""
Unified deployment script for BioLM models.

This script handles both single-variant and multi-variant model deployments
by leveraging the ModelFamily configuration defined in each model's config.py.

Usage via bh CLI:
    # Deploy a model's default variant (the first-declared; smallest for most families)
    bh deploy esm2

    # Deploy every variant of the family
    bh deploy esm2 --all-variants

    # Deploy a specific variant
    bh deploy esm2 --variant MODEL_SIZE=150m

    # Deploy multiple models (default variant each)
    bh deploy esm2 esmc esmfold --force

Credentials: if the Modal workspace has no `cloudflare-r2` secret, the deploy
auto-switches to credential-less mode (public weights read over HTTP, no
self-population). Set BIOLM_SKIP_MODAL_SECRETS explicitly to override the
auto-detection in either direction.
"""

console = Console()


def deploy_single_variant(
    model_name: str, variant_env_vars: dict[str, str], force: bool = False
) -> bool:
    """Deploy a single model variant using subprocess to ensure clean environment."""
    # Build the command
    model_path = Path(__file__).parent.parent / "models" / model_name / "app.py"

    if force:
        print("  🚀 Force deployment enabled (--force flag active)")

    # Set environment variables in the subprocess call
    env = os.environ.copy()
    env.update(variant_env_vars)

    # Build command
    cmd = [sys.executable, str(model_path)]
    if force:
        cmd.append("--force-deploy")

    # Format and display the command being executed
    if variant_env_vars:
        env_str = " ".join(f"{k}={v}" for k, v in variant_env_vars.items())
        print(f"  Executing: {env_str} {' '.join(cmd)}")
    else:
        print(f"  Executing: {' '.join(cmd)}")

    try:
        # When force=True, disable stdin to prevent any interactive prompts
        # and capture output for better error reporting
        if force:
            result = subprocess.run(
                cmd,
                env=env,
                check=True,
                stdin=subprocess.DEVNULL,  # Prevent any input prompts
                capture_output=True,
                text=True,
            )
            print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
        else:
            # Allow interactive prompts when not forcing
            subprocess.run(cmd, env=env, check=True)
        return True
    except subprocess.CalledProcessError as e:
        # Print captured output on error
        if hasattr(e, "stdout") and e.stdout:
            print(e.stdout)
        if hasattr(e, "stderr") and e.stderr:
            print(e.stderr, file=sys.stderr)
        return False


def get_model_family(model_name: str) -> Optional[ModelFamily]:
    """Load the ModelFamily from a model's config.py."""
    try:
        # Handle both model directory names and slugs
        module_package_name = model_name.replace("-", "_")
        config_module = import_module(f"models.{module_package_name}.config")

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


# Main deploy command function
def deploy_cmd(
    models: Annotated[
        list[str],
        typer.Argument(help="Model(s) to deploy (e.g., esm2 esmc esmfold)"),
    ],
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
            help="Deploy every variant of the family (default: just the "
            "default/first variant)",
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
) -> None:
    """
    Deploy one or more BioLM models.

    By default deploys each model's single default variant; pass --all-variants
    for the whole family or --variant KEY=value for a specific one. If the Modal
    workspace has no cloudflare-r2 secret, the deploy auto-switches to
    credential-less mode (public weights over HTTP).

    Examples:
        bh deploy esm2
        bh deploy esm2 --all-variants
        bh deploy esm2 --variant MODEL_SIZE=150m
        bh deploy esm2 --cache          # enable response caching for this deploy
        bh deploy esm2 esmc esmfold --force
    """

    # Consolidate force flags
    force = force or force_deploy

    # Auto-detect credential-less mode (no cloudflare-r2 secret) once per invocation,
    # before spawning any deploy subprocess. Must run here (authenticated CLI), not at
    # app.py import time.
    _maybe_enable_credential_less()

    # Response caching is a deploy-time setting read inside the container via
    # BIOLM_CACHE_ENABLED. The deploy subprocess inherits os.environ, so set it
    # here. Default (None) leaves any pre-existing export untouched; --cache
    # forces it on, --no-cache forces it off.
    if cache is True:
        os.environ["BIOLM_CACHE_ENABLED"] = "1"
    elif cache is False:
        os.environ.pop("BIOLM_CACHE_ENABLED", None)

    # Deploy each model
    for model_name in models:
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
