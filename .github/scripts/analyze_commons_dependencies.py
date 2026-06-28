import ast
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

"""
Simplified commons dependency analyzer using the naive but effective approach.

This implementation:
1. Maps all imports from each model (not just used ones)
2. Tracks ALL symbol types including variables, constants, functions, classes
3. Uses simple pattern matching on git diff
4. Provides clear, debuggable logic
"""

# Critical commons files that affect all models through transitive dependencies.
# Changes to these files should trigger redeployment of ALL models because they
# are used indirectly by every model (e.g., through decorators, mixins, etc.)
# even if models don't directly import from them.
CRITICAL_COMMONS_FILES = {
    # Caching is used by @modal_endpoint decorator which all models use
    "models/commons/core/caching.py",
    # The decorator itself - all models use @modal_endpoint
    "models/commons/core/decorator.py",
    # Base request/response pydantic models used by all schemas
    "models/commons/model/pydantic.py",
}


class DependencyAnalyzer:
    """
    Simple, effective dependency analyzer.

    Philosophy: Better to over-test (include models that might not need it)
    than under-test (miss models that do need it).
    """

    def __init__(self):
        # model_name -> {module -> set of imported symbols}
        self.model_imports: dict[str, dict[str, set[str]]] = defaultdict(
            lambda: defaultdict(set)
        )

        # Reverse mapping: "module.symbol" -> set of models
        self.symbol_to_models: dict[str, set[str]] = defaultdict(set)

    def should_scan_file(self, file_path: Path) -> bool:
        """Determine if a file should be scanned for commons imports.

        Only scans models/{model_name}/*.py (direct children).
        Excludes commons, scripts, __pycache__, and all subdirectories.
        Includes test files (they may import commons too).
        """
        parts = file_path.parts

        if len(parts) < 3 or parts[0] != "models":
            return False

        if parts[1] in ["commons", "scripts", "__pycache__"]:
            return False

        # Only direct .py files, not in subdirectories
        if len(parts) > 3:
            return False

        return file_path.suffix == ".py"

    def extract_all_imports(self, file_path: Path) -> dict[str, set[str]]:
        """
        Extract ALL imports from a Python file.

        Returns:
            Dict mapping module names to sets of imported symbols
        """
        imports = defaultdict(set)

        try:
            content = file_path.read_text()
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    # import models.commons.core.decorator
                    for alias in node.names:
                        if alias.name.startswith("models.commons"):
                            # Track the entire module as imported
                            imports[alias.name].add(
                                "*"
                            )  # Wildcard for module-level import

                elif isinstance(node, ast.ImportFrom):
                    # from models.commons.core.decorator import biolm_modal_endpoint
                    if node.module and node.module.startswith("models.commons"):
                        for alias in node.names:
                            if alias.name == "*":
                                # from module import *
                                imports[node.module].add("*")
                            else:
                                # Specific symbol import
                                imports[node.module].add(alias.name)

        except (OSError, SyntaxError) as e:
            print(f"  ⚠️ Error parsing {file_path}: {e}")

        return dict(imports)

    def build_import_map(self):
        """Build the complete import mapping for all models."""
        print("🔍 Building import map (naive approach)...")

        models_dir = Path("models")
        model_count = 0
        file_count = 0

        for model_dir in models_dir.iterdir():
            if not model_dir.is_dir():
                continue

            model_name = model_dir.name
            if model_name in ["commons", "scripts", "__pycache__"]:
                continue

            model_count += 1

            # Scan all Python files in this model
            for py_file in model_dir.glob("*.py"):
                if not self.should_scan_file(py_file):
                    continue

                file_count += 1
                imports = self.extract_all_imports(py_file)

                # Add to model imports
                for module, symbols in imports.items():
                    self.model_imports[model_name][module].update(symbols)

                    # Build reverse mapping
                    for symbol in symbols:
                        key = f"{module}.{symbol}"
                        self.symbol_to_models[key].add(model_name)

                    # Register module-level wildcard so that diff-detected
                    # wildcards (e.g., method-level changes inside imported
                    # classes) resolve back to models with selective imports.
                    self.symbol_to_models[f"{module}.*"].add(model_name)

        print(f"✅ Scanned {file_count} files across {model_count} models")
        print(f"   Found {len(self.symbol_to_models)} unique import patterns")

    def extract_changed_symbols_from_diff(
        self, diff_output: str
    ) -> dict[str, set[str]]:
        """
        Extract ALL changed symbols from git diff.

        This includes:
        - Functions: def func_name()
        - Classes: class ClassName:
        - Methods: def method_name(self)
        - Variables: VARIABLE_NAME = value
        - Constants: CONSTANT = 123
        - Type aliases: TypeName = Union[...]
        """
        changed = defaultdict(set)
        current_file = None

        # Comprehensive patterns
        patterns = {
            "function": re.compile(r"^[+-]\s*def\s+(\w+)\s*\("),
            "class": re.compile(r"^[+-]\s*class\s+(\w+)\s*[\(:]"),
            "method": re.compile(r"^[+-]\s+def\s+(\w+)\s*\("),  # Indented
            "variable": re.compile(
                r"^[+-]\s*([A-Z_][A-Z0-9_]*)\s*[:=]"
            ),  # CAPS variables
            "typed_var": re.compile(
                r"^[+-]\s*(\w+)\s*:\s*\w+\s*="
            ),  # name: type = value
            "assignment": re.compile(r"^[+-]\s*(\w+)\s*="),  # Simple assignments
        }

        for line in diff_output.split("\n"):
            # Track current file
            if line.startswith("diff --git"):
                parts = line.split()
                if len(parts) >= 3:
                    current_file = (
                        parts[2][2:] if parts[2].startswith("a/") else parts[2]
                    )

            # Skip if not in commons
            if not current_file or not current_file.startswith("models/commons/"):
                continue

            # Check all patterns
            for _pattern_name, pattern in patterns.items():
                match = pattern.match(line)
                if match:
                    symbol = match.group(1)
                    changed[current_file].add(symbol)
                    # Also track that "something" changed in this file
                    changed[current_file].add("*")  # Wildcard for any change

        return dict(changed)

    def _process_symbol_changes(self, module_path: str, symbols: set[str]) -> set[str]:
        """Process symbol changes and return affected models."""
        affected = set()
        for symbol in symbols:
            # Check both specific symbol and wildcard imports
            specific_key = f"{module_path}.{symbol}"
            wildcard_key = f"{module_path}.*"

            # Models that import this specific symbol
            if specific_key in self.symbol_to_models:
                affected.update(self.symbol_to_models[specific_key])

            # Models that import * from this module
            if wildcard_key in self.symbol_to_models:
                affected.update(self.symbol_to_models[wildcard_key])
        return affected

    def _process_conservative_matching(self, module_path: str) -> set[str]:
        """Conservative matching when no symbol info available."""
        affected = set()
        for model, imports in self.model_imports.items():
            for import_module in imports.keys():
                # Check if this import is from the changed module
                if import_module == module_path or import_module.startswith(
                    f"{module_path}."
                ):
                    affected.add(model)
                    break
        return affected

    def get_affected_models(
        self, changed_files: list[str], diff_output: str = None
    ) -> tuple[set[str], dict]:
        """
        Get models affected by commons changes.

        Uses a conservative approach: if we can't determine specific symbols,
        assume ALL models importing from that module are affected.

        Critical files (like caching.py, decorator.py) automatically trigger
        all models because they're used transitively by every model.
        """
        affected_models = set()
        analysis = {
            "method": "naive-safe",
            "changed_files": changed_files,
            "changed_symbols": {},
            "import_matches": [],
            "critical_files_changed": [],
        }

        # Check for critical files first - these affect ALL models
        critical_files_changed = [
            f for f in changed_files if f in CRITICAL_COMMONS_FILES
        ]
        if critical_files_changed:
            analysis["critical_files_changed"] = critical_files_changed
            print(f"  🚨 Critical commons files changed: {critical_files_changed}")
            print("     These affect all models through transitive dependencies")
            # Return ALL models
            all_models = set()
            for model_dir in Path("models").iterdir():
                if model_dir.is_dir() and model_dir.name not in [
                    "commons",
                    "scripts",
                    "__pycache__",
                ]:
                    all_models.add(model_dir.name)
            return all_models, analysis

        # Extract changed symbols if we have diff
        if diff_output:
            analysis["changed_symbols"] = self.extract_changed_symbols_from_diff(
                diff_output
            )

        for file_path in changed_files:
            if not file_path.startswith("models/commons/"):
                continue

            # Convert file path to module path
            module_path = file_path.replace("/", ".").replace(".py", "")

            # Check for specific symbol changes
            if file_path in analysis["changed_symbols"]:
                symbols = analysis["changed_symbols"][file_path]
                print(f"  📝 {file_path}: {len(symbols)} symbols changed")
                symbol_matched = self._process_symbol_changes(module_path, symbols)
                if symbol_matched:
                    affected_models.update(symbol_matched)
                else:
                    # Symbols were detected in the diff but none matched import
                    # map entries (e.g., method-level changes inside a class).
                    # Fall back to conservative matching to avoid silent misses.
                    print(
                        f"  ⚠️ No symbol matches for {file_path}, "
                        "falling back to conservative approach"
                    )
                    affected_models.update(
                        self._process_conservative_matching(module_path)
                    )
            else:
                # No specific symbol info - be conservative
                print(
                    f"  ⚠️ No symbol info for {file_path}, using conservative approach"
                )
                affected_models.update(self._process_conservative_matching(module_path))

        return affected_models, analysis

    def generate_comparison_report(
        self, changed_files: list[str], diff_output: str = None
    ) -> dict:
        """Generate a comparison report."""
        # Get all models
        all_models = set()
        for model_dir in Path("models").iterdir():
            if model_dir.is_dir() and model_dir.name not in [
                "commons",
                "scripts",
                "__pycache__",
            ]:
                all_models.add(model_dir.name)

        # Get affected models
        affected_models, analysis = self.get_affected_models(changed_files, diff_output)

        # Calculate savings
        models_saved = len(all_models) - len(affected_models)
        percentage_saved = (
            round((models_saved / len(all_models)) * 100, 1) if all_models else 0
        )

        return {
            "method": "naive-safe (includes all imports, not just used symbols)",
            "changed_files": changed_files,
            "changed_symbols": analysis["changed_symbols"],
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


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Naive but safe dependency analysis")
    parser.add_argument(
        "--changed-files", type=str, help="Comma-separated changed files"
    )
    parser.add_argument("--base-ref", default="HEAD^", help="Git reference for diff")
    parser.add_argument(
        "--compare", action="store_true", help="Generate comparison report"
    )

    args = parser.parse_args()

    analyzer = DependencyAnalyzer()
    analyzer.build_import_map()

    if args.changed_files:
        changed_files = args.changed_files.split(",")

        # Get git diff
        try:
            result = subprocess.run(
                ["git", "diff", args.base_ref, "HEAD", "--"] + changed_files,
                capture_output=True,
                text=True,
                timeout=30,
            )
            diff_output = result.stdout if result.returncode == 0 else None
        except Exception:
            diff_output = None

        if args.compare:
            report = analyzer.generate_comparison_report(changed_files, diff_output)
            print(json.dumps(report, indent=2))
        else:
            affected_models, _ = analyzer.get_affected_models(
                changed_files, diff_output
            )
            print(json.dumps(sorted(affected_models)))

    else:
        print("Import map built successfully")


if __name__ == "__main__":
    main()
