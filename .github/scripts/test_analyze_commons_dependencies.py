"""Test suite for the commons dependency analyzer.

Tests the dependency analysis that:
- Maps all imports from each model
- Detects changes including variables, constants, functions, classes
- Uses conservative matching (better to over-test than under-test)
"""

import tempfile
from pathlib import Path

from analyze_commons_dependencies import CRITICAL_COMMONS_FILES, DependencyAnalyzer


def _get_current_models() -> set[str]:
    """Get all current valid models in the repository."""
    models = set()
    models_dir = Path("models")
    for item in models_dir.iterdir():
        if item.is_dir() and item.name not in ["commons", "scripts", "__pycache__"]:
            models.add(item.name)
    return models


class TestFileFiltering:
    """Test that file filtering correctly includes/excludes appropriate files."""

    def test_direct_model_app_file(self):
        analyzer = DependencyAnalyzer()
        assert analyzer.should_scan_file(Path("models/esm2/app.py")) is True

    def test_direct_model_schema_file(self):
        analyzer = DependencyAnalyzer()
        assert analyzer.should_scan_file(Path("models/esm2/schema.py")) is True

    def test_direct_model_config_file(self):
        analyzer = DependencyAnalyzer()
        assert analyzer.should_scan_file(Path("models/esm2/config.py")) is True

    def test_test_files_included(self):
        analyzer = DependencyAnalyzer()
        assert analyzer.should_scan_file(Path("models/esm2/test.py")) is True

    def test_external_subdirectory_excluded(self):
        analyzer = DependencyAnalyzer()
        assert analyzer.should_scan_file(Path("models/esm2/external/lib.py")) is False

    def test_fixtures_subdirectory_excluded(self):
        analyzer = DependencyAnalyzer()
        assert analyzer.should_scan_file(Path("models/esm2/fixtures/data.py")) is False

    def test_commons_excluded(self):
        analyzer = DependencyAnalyzer()
        assert (
            analyzer.should_scan_file(Path("models/commons/core/decorator.py")) is False
        )

    def test_scripts_excluded(self):
        analyzer = DependencyAnalyzer()
        assert analyzer.should_scan_file(Path("models/scripts/deploy.py")) is False

    def test_pycache_excluded(self):
        analyzer = DependencyAnalyzer()
        assert analyzer.should_scan_file(Path("models/__pycache__/cached.py")) is False


class TestImportExtraction:
    """Test extraction of imports from Python files."""

    def test_extracts_all_commons_import_styles(self):
        test_content = """\
from models.commons.core.decorator import modal_endpoint
from models.commons.data.request_response import *
import models.commons.modal.deployment
from models.commons.model.config import ModelFamily

# Non-commons imports (should be ignored)
import torch
from transformers import AutoModel
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(test_content)
            temp_path = Path(f.name)

        try:
            analyzer = DependencyAnalyzer()
            imports = analyzer.extract_all_imports(temp_path)

            expected = {
                "models.commons.core.decorator": {"modal_endpoint"},
                "models.commons.data.request_response": {"*"},
                "models.commons.modal.deployment": {"*"},
                "models.commons.model.config": {"ModelFamily"},
            }

            for module, expected_symbols in expected.items():
                assert module in imports, f"Missing module: {module}"
                assert (
                    imports[module] == expected_symbols
                ), f"Wrong symbols for {module}: expected {expected_symbols}, got {imports[module]}"

            assert "torch" not in imports, "Non-commons imports should be excluded"
            assert (
                "transformers" not in imports
            ), "Non-commons imports should be excluded"
        finally:
            temp_path.unlink(missing_ok=True)


class TestChangeDetection:
    """Test detection of changed symbols from git diff."""

    FAKE_DIFF = """\
diff --git a/models/commons/core/decorator.py b/models/commons/core/decorator.py
index abc123..def456 100644
--- a/models/commons/core/decorator.py
+++ b/models/commons/core/decorator.py
@@ -10,7 +10,7 @@
-class ModalEndpoint:
+class ModalEndpoint:  # Modified
     def __call__(self):
         pass

-def modal_endpoint():
+def modal_endpoint(new_param):
    pass

diff --git a/models/commons/config/settings.py b/models/commons/config/settings.py
index 111222..333444 100644
--- a/models/commons/config/settings.py
+++ b/models/commons/config/settings.py
-MAX_RETRIES = 3
+MAX_RETRIES = 5
-DEFAULT_TIMEOUT: int = 30
+DEFAULT_TIMEOUT: int = 60
+NEW_SETTING = "value"
"""

    def test_detects_correct_files(self):
        analyzer = DependencyAnalyzer()
        changed = analyzer.extract_changed_symbols_from_diff(self.FAKE_DIFF)
        assert set(changed.keys()) == {
            "models/commons/core/decorator.py",
            "models/commons/config/settings.py",
        }

    def test_detects_class_change(self):
        analyzer = DependencyAnalyzer()
        changed = analyzer.extract_changed_symbols_from_diff(self.FAKE_DIFF)
        assert "ModalEndpoint" in changed["models/commons/core/decorator.py"]

    def test_detects_function_change(self):
        analyzer = DependencyAnalyzer()
        changed = analyzer.extract_changed_symbols_from_diff(self.FAKE_DIFF)
        assert "modal_endpoint" in changed["models/commons/core/decorator.py"]

    def test_detects_variable_change(self):
        analyzer = DependencyAnalyzer()
        changed = analyzer.extract_changed_symbols_from_diff(self.FAKE_DIFF)
        assert "MAX_RETRIES" in changed["models/commons/config/settings.py"]

    def test_detects_typed_variable_change(self):
        analyzer = DependencyAnalyzer()
        changed = analyzer.extract_changed_symbols_from_diff(self.FAKE_DIFF)
        assert "DEFAULT_TIMEOUT" in changed["models/commons/config/settings.py"]

    def test_wildcard_always_present(self):
        analyzer = DependencyAnalyzer()
        changed = analyzer.extract_changed_symbols_from_diff(self.FAKE_DIFF)
        for symbols in changed.values():
            assert "*" in symbols, "Wildcard should be present for any changed file"


class TestConservativeMatching:
    """Test that the analyzer uses conservative matching when appropriate."""

    def _build_analyzer_with_stub_imports(self):
        """Build analyzer with stub imports using a NON-critical commons file.

        Uses models.commons.model.config instead of core.decorator because
        core/decorator.py is in CRITICAL_COMMONS_FILES which triggers ALL models
        before symbol matching logic runs.
        """
        analyzer = DependencyAnalyzer()
        analyzer.model_imports = {
            "esm2": {
                "models.commons.model.config": {"ModelFamily"},
                "models.commons.core.decorator": {"modal_endpoint"},
            },
            "evo": {
                "models.commons.model.config": {"biolm_model_class"},
            },
            "chai1": {
                "models.commons.model.config": {"*"},
            },
        }
        # Build reverse mapping (mirrors build_import_map behavior)
        for model, imports in analyzer.model_imports.items():
            for module, symbols in imports.items():
                for symbol in symbols:
                    key = f"{module}.{symbol}"
                    analyzer.symbol_to_models[key].add(model)
                # Register module-level wildcard (matches build_import_map)
                analyzer.symbol_to_models[f"{module}.*"].add(model)
        return analyzer

    def test_module_change_affects_all_importers(self):
        """Any change to a module triggers all models importing from it.

        Smart mode optimizes at the module level (not symbol level): only
        models importing from the changed module are affected, rather than
        ALL models (which is what default mode does).
        """
        analyzer = self._build_analyzer_with_stub_imports()
        changed_files = ["models/commons/model/config.py"]
        diff = "-class ModelFamily:\n+class ModelFamily:  # Modified\n"
        changed_symbols = {"models/commons/model/config.py": {"ModelFamily"}}
        analyzer.extract_changed_symbols_from_diff = lambda x: changed_symbols

        affected, _ = analyzer.get_affected_models(changed_files, diff)

        # All three import from models.commons.model.config — all should be affected
        assert "esm2" in affected
        assert "evo" in affected
        assert "chai1" in affected

    def test_unrelated_module_not_affected(self):
        """Models that don't import from the changed module are not affected."""
        analyzer = self._build_analyzer_with_stub_imports()
        changed_files = ["models/commons/storage/r2.py"]
        changed_symbols = {"models/commons/storage/r2.py": {"upload_to_r2"}}
        analyzer.extract_changed_symbols_from_diff = lambda x: changed_symbols

        affected, _ = analyzer.get_affected_models(changed_files, "fake diff")

        # No model in the stub imports from models.commons.storage.r2
        assert (
            len(affected) == 0
        ), f"No stub models import from storage.r2, but got: {affected}"

    def test_method_level_change_detected_via_wildcard(self):
        """Regression test: method-level changes inside an imported class.

        When the diff touches a method (e.g., `def get_app_config`) inside
        a class that models import by name, the diff parser emits
        `{"get_app_config", "*"}`. The wildcard must resolve to all models
        importing from that module.
        """
        analyzer = self._build_analyzer_with_stub_imports()
        changed_files = ["models/commons/model/config.py"]
        changed_symbols = {"models/commons/model/config.py": {"get_app_config", "*"}}
        analyzer.extract_changed_symbols_from_diff = lambda x: changed_symbols

        affected, _ = analyzer.get_affected_models(changed_files, "fake diff")

        # All three models import from models.commons.model.config,
        # so the wildcard should match all of them via module-level wildcard
        assert "esm2" in affected, "esm2 should be affected via module wildcard"
        assert "evo" in affected, "evo should be affected via module wildcard"
        assert "chai1" in affected, "chai1 should be affected via module wildcard"

    def test_fail_open_when_no_symbol_matches(self):
        """When diff symbols exist but none match the import map, fall back
        to conservative matching (all models importing from that module)."""
        analyzer = DependencyAnalyzer()
        analyzer.model_imports = {
            "testmodel": {
                "models.commons.util.environment": {"parse_variant"},
            },
        }
        # Only register the specific symbol — no module wildcard
        analyzer.symbol_to_models["models.commons.util.environment.parse_variant"].add(
            "testmodel"
        )

        changed_files = ["models/commons/util/environment.py"]
        # Diff has a symbol that doesn't match anything in the import map
        changed_symbols = {"models/commons/util/environment.py": {"_internal_helper"}}
        analyzer.extract_changed_symbols_from_diff = lambda x: changed_symbols

        affected, _ = analyzer.get_affected_models(changed_files, "fake diff")

        assert (
            "testmodel" in affected
        ), "Should fall back to conservative matching when no symbols match"


class TestBuildImportMap:
    """Test building the complete import map for all models."""

    def test_import_map_has_models(self):
        analyzer = DependencyAnalyzer()
        analyzer.build_import_map()
        assert len(analyzer.model_imports) > 0, "Should find at least one model"

    def test_reverse_mapping_built(self):
        analyzer = DependencyAnalyzer()
        analyzer.build_import_map()
        assert len(analyzer.symbol_to_models) > 0, "Should build reverse mapping"

    def test_known_model_has_imports(self):
        analyzer = DependencyAnalyzer()
        analyzer.build_import_map()
        if "esm2" in analyzer.model_imports:
            assert (
                len(analyzer.model_imports["esm2"]) > 0
            ), "ESM2 should import from commons"


class TestCriticalFiles:
    """Test that critical files trigger all models."""

    def test_each_critical_file_triggers_all_models(self):
        analyzer = DependencyAnalyzer()
        analyzer.build_import_map()
        all_models = _get_current_models()

        for critical_file in CRITICAL_COMMONS_FILES:
            affected, analysis = analyzer.get_affected_models([critical_file])
            assert affected == all_models, (
                f"Critical file {critical_file} should affect all {len(all_models)} "
                f"models, but only affected {len(affected)}"
            )
            assert critical_file in analysis.get(
                "critical_files_changed", []
            ), f"Critical file {critical_file} not marked as critical in analysis"


class TestRealScenario:
    """Test with a real scenario comparing old vs new approach."""

    def test_smart_analysis_tests_fewer_or_equal_models(self):
        analyzer = DependencyAnalyzer()
        analyzer.build_import_map()

        changed_files = ["models/commons/model/config.py"]
        fake_diff = (
            "diff --git a/models/commons/model/config.py "
            "b/models/commons/model/config.py\n"
            "-class ModelFamily:\n"
            "+class ModelFamily:  # Modified\n"
        )

        report = analyzer.generate_comparison_report(changed_files, fake_diff)
        assert report["new_way"]["models_tested"] <= report["old_way"]["models_tested"]
