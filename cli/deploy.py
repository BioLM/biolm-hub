import os
import subprocess
import sys
from importlib import import_module
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

"""
Unified deployment script for BioLM models.

This script handles both single-variant and multi-variant model deployments
by leveraging the ModelFamily configuration defined in each model's config.py.

Usage via bm CLI:
    # Deploy a single model (all variants)
    bm deploy esm2

    # Deploy with force flag
    bm deploy esm2 --force

    # Deploy specific variant
    bm deploy esm2 --variant MODEL_SIZE=150m

    # Deploy multiple models
    bm deploy esm2 esmc esmfold --force
"""

console = Console()


def deploy_single_variant(
    model_name: str, variant_env_vars: dict, force: bool = False
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
            result = subprocess.run(cmd, env=env, check=True)
        return True
    except subprocess.CalledProcessError as e:
        # Print captured output on error
        if hasattr(e, "stdout") and e.stdout:
            print(e.stdout)
        if hasattr(e, "stderr") and e.stderr:
            print(e.stderr, file=sys.stderr)
        return False


def get_model_family(model_name: str):
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

        return config_module.MODEL_FAMILY
    except ImportError as e:
        print(f"❌ ERROR: Could not import models/{model_name}/config.py: {e}")
        return None


def parse_variant_spec(variant_spec: str) -> dict:
    """Parse variant specification like 'MODEL_SIZE=150m,MODEL_ACTION=encode'."""
    if not variant_spec:
        return {}

    variant_dict = {}
    for pair in variant_spec.split(","):
        if "=" not in pair:
            print(f"❌ ERROR: Invalid variant spec format: {pair}")
            print("Expected format: KEY=value or KEY1=value1,KEY2=value2")
            sys.exit(1)
        key, value = pair.split("=", 1)
        variant_dict[key.strip()] = value.strip()

    return variant_dict


def _get_variants_to_deploy(model_family, variant_spec):
    """Get the list of variants to deploy based on variant_spec."""
    if variant_spec:
        # Deploy specific variant
        variant_dict = parse_variant_spec(variant_spec)
        try:
            variant = model_family.find_variant(**variant_dict)
            variants_to_deploy = [variant]
            print(f"Deploying specific variant: {variant.modal_app_name}")
        except ValueError as e:
            print(f"❌ ERROR: {e}")
            sys.exit(1)
    else:
        # Deploy all variants
        variants_to_deploy = model_family.resolved_variants
        if len(variants_to_deploy) > 1:
            print(f"Multi-variant model with {len(variants_to_deploy)} variants")

    return variants_to_deploy


def _deploy_variants(model_name, variants_to_deploy, force):
    """Deploy a list of variants and track failures."""
    failed_deployments = []

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


def _print_deployment_summary(model_name, variants_to_deploy, failed_deployments):
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


def deploy_model(model_name: str, force: bool = False, variant_spec: str = None):
    """
    Deploy a model and all its variants, or a specific variant if specified.

    Args:
        model_name: Name of the model directory (e.g., "esm2", "esmfold")
        force: Whether to force deployment without prompts
        variant_spec: Optional specific variant to deploy (e.g., "MODEL_SIZE=150m")
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
    variants_to_deploy = _get_variants_to_deploy(model_family, variant_spec)

    # Deploy each variant
    failed_deployments = _deploy_variants(model_name, variants_to_deploy, force)

    # Print summary
    _print_deployment_summary(model_name, variants_to_deploy, failed_deployments)


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
):
    """
    Deploy one or more BioLM models.

    Examples:
        bm deploy esm2
        bm deploy esm2 --force
        bm deploy esm2 --variant MODEL_SIZE=150m
        bm deploy esm2 esmc esmfold --force
    """

    # Consolidate force flags
    force = force or force_deploy

    # Deploy each model
    for model_name in models:
        try:
            deploy_model(model_name=model_name, force=force, variant_spec=variant)
        except SystemExit as e:
            if e.code != 0:
                console.print(f"[red]❌ Deployment for {model_name} failed![/red]")
                sys.exit(1)
        except Exception as e:
            console.print(f"[red]❌ Error deploying {model_name}: {e}[/red]")
            sys.exit(1)
