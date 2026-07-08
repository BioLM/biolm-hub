"""Module-granular commons dependency analyzer.

Maps each model to the set of ``models.commons`` modules it imports, then for a
set of changed commons files returns every model importing the corresponding
module. Changes to ``CRITICAL_COMMONS_FILES`` (used transitively by every model
via decorators/mixins/base models) trigger ALL models.

Philosophy: better to over-test (include a model that might not need it) than
under-test (miss a model that does). The analysis is intentionally
module-granular. An earlier version attempted symbol-level (per-function /
per-constant) diff analysis, but it always degraded to the same module-level
result while adding ~300 lines of fragile diff/regex code, so it was removed.
"""

import ast
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

# Directories under models/ that are not model implementations.
EXCLUDED_MODEL_DIRS = {"commons", "scripts", "__pycache__"}

# Critical commons files that affect all models through transitive dependencies.
# Changes to these files should trigger redeployment of ALL models because they
# are used indirectly by every model (e.g., through decorators, mixins, base
# pydantic models) even if models don't directly import from them.
CRITICAL_COMMONS_FILES = {
    # Caching is used by @modal_endpoint decorator which all models use
    "models/commons/core/caching.py",
    # The decorator itself - all models use @modal_endpoint
    "models/commons/core/decorator.py",
    # Base request/response pydantic models used by all schemas
    "models/commons/model/pydantic.py",
}


class DependencyAnalyzer:
    """Module-granular commons dependency analyzer.

    Philosophy: better to over-test (include models that might not need it)
    than under-test (miss models that do need it).
    """

    def __init__(self) -> None:
        # model_name -> set of imported `models.commons` modules
        self.model_imports: dict[str, set[str]] = defaultdict(set)

    def should_scan_file(self, file_path: Path) -> bool:
        """Determine if a file should be scanned for commons imports.

        Only scans models/{model_name}/*.py (direct children).
        Excludes commons, scripts, __pycache__, and all subdirectories.
        Includes test files (they may import commons too).
        """
        parts = file_path.parts

        if len(parts) < 3 or parts[0] != "models":
            return False

        if parts[1] in EXCLUDED_MODEL_DIRS:
            return False

        # Only direct .py files, not in subdirectories
        if len(parts) > 3:
            return False

        return file_path.suffix == ".py"

    def extract_imported_modules(self, file_path: Path) -> set[str]:
        """Return the set of ``models.commons`` modules imported by a file.

        Handles both ``import models.commons.x`` and
        ``from models.commons.x import y`` forms; the imported symbols are
        intentionally not tracked (analysis is module-granular).
        """
        modules: set[str] = set()

        try:
            tree = ast.parse(file_path.read_text())
        except (OSError, SyntaxError) as e:
            print(f"  ⚠️ Error parsing {file_path}: {e}")
            return modules

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                # import models.commons.core.decorator
                for alias in node.names:
                    if alias.name.startswith("models.commons"):
                        modules.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                # from models.commons.core.decorator import modal_endpoint
                if node.module and node.module.startswith("models.commons"):
                    modules.add(node.module)

        return modules

    def build_import_map(self) -> None:
        """Build the complete commons-import mapping for all models."""
        print("🔍 Building commons import map (module-granular)...")

        models_dir = Path("models")
        model_count = 0
        file_count = 0

        for model_dir in models_dir.iterdir():
            if not model_dir.is_dir() or model_dir.name in EXCLUDED_MODEL_DIRS:
                continue

            model_count += 1

            for py_file in model_dir.glob("*.py"):
                if not self.should_scan_file(py_file):
                    continue

                file_count += 1
                self.model_imports[model_dir.name].update(
                    self.extract_imported_modules(py_file)
                )

        print(f"✅ Scanned {file_count} files across {model_count} models")

    def _all_models(self) -> set[str]:
        """Return every valid model directory under models/."""
        return {
            model_dir.name
            for model_dir in Path("models").iterdir()
            if model_dir.is_dir() and model_dir.name not in EXCLUDED_MODEL_DIRS
        }

    def _models_importing_module(self, module_path: str) -> set[str]:
        """All models importing the given commons module (or a submodule)."""
        affected = set()
        for model, modules in self.model_imports.items():
            for imported in modules:
                if imported == module_path or imported.startswith(f"{module_path}."):
                    affected.add(model)
                    break
        return affected

    def get_affected_models(
        self, changed_files: list[str]
    ) -> tuple[set[str], dict[str, Any]]:
        """Get models affected by commons changes (module granularity).

        Any change to a commons module triggers all models importing that
        module. Critical files (caching.py, decorator.py, pydantic.py) trigger
        ALL models because they're used transitively by every model.
        """
        analysis: dict[str, Any] = {
            "method": "module-granular",
            "changed_files": changed_files,
            "critical_files_changed": [],
        }

        # Critical files first - these affect ALL models.
        critical_files_changed = [
            f for f in changed_files if f in CRITICAL_COMMONS_FILES
        ]
        if critical_files_changed:
            analysis["critical_files_changed"] = critical_files_changed
            print(f"  🚨 Critical commons files changed: {critical_files_changed}")
            print("     These affect all models through transitive dependencies")
            return self._all_models(), analysis

        affected_models: set[str] = set()
        for file_path in changed_files:
            if not file_path.startswith("models/commons/"):
                continue

            module_path = file_path.replace("/", ".").replace(".py", "")
            matched = self._models_importing_module(module_path)
            print(f"  📝 {file_path}: {len(matched)} model(s) import this module")
            affected_models.update(matched)

        return affected_models, analysis

    def generate_comparison_report(self, changed_files: list[str]) -> dict[str, Any]:
        """Generate a comparison report (old all-models vs module-granular)."""
        all_models = self._all_models()
        affected_models, analysis = self.get_affected_models(changed_files)

        models_saved = len(all_models) - len(affected_models)
        percentage_saved = (
            round((models_saved / len(all_models)) * 100, 1) if all_models else 0
        )

        return {
            "method": "module-granular",
            "changed_files": changed_files,
            "old_way": {"models_tested": len(all_models), "models": sorted(all_models)},
            "new_way": {
                "models_tested": len(affected_models),
                "models": sorted(affected_models),
            },
            "savings": {
                "models_saved": models_saved,
                "percentage_saved": percentage_saved,
                "estimated_minutes_saved": models_saved * 3,
            },
            "details": analysis,
        }


def main() -> None:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Module-granular dependency analysis")
    parser.add_argument(
        "--changed-files", type=str, help="Comma-separated changed files"
    )
    parser.add_argument(
        "--compare", action="store_true", help="Generate comparison report"
    )

    args = parser.parse_args()

    analyzer = DependencyAnalyzer()
    analyzer.build_import_map()

    if args.changed_files:
        changed_files = args.changed_files.split(",")

        if args.compare:
            report = analyzer.generate_comparison_report(changed_files)
            print(json.dumps(report, indent=2))
        else:
            affected_models, _ = analyzer.get_affected_models(changed_files)
            print(json.dumps(sorted(affected_models)))
    else:
        print("Import map built successfully")


if __name__ == "__main__":
    main()
