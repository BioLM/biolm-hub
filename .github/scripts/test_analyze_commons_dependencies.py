"""Test suite for the module-granular commons dependency analyzer.

Tests the dependency analysis that:
- Maps the commons modules each model imports
- Returns all models importing a changed commons module (module granularity)
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

    def test_direct_model_app_file(self) -> None:
        analyzer = DependencyAnalyzer()
        assert analyzer.should_scan_file(Path("models/esm2/app.py")) is True

    def test_direct_model_schema_file(self) -> None:
        analyzer = DependencyAnalyzer()
        assert analyzer.should_scan_file(Path("models/esm2/schema.py")) is True

    def test_direct_model_config_file(self) -> None:
        analyzer = DependencyAnalyzer()
        assert analyzer.should_scan_file(Path("models/esm2/config.py")) is True

    def test_test_files_included(self) -> None:
        analyzer = DependencyAnalyzer()
        assert analyzer.should_scan_file(Path("models/esm2/test.py")) is True

    def test_external_subdirectory_excluded(self) -> None:
        analyzer = DependencyAnalyzer()
        assert analyzer.should_scan_file(Path("models/esm2/external/lib.py")) is False

    def test_fixtures_subdirectory_excluded(self) -> None:
        analyzer = DependencyAnalyzer()
        assert analyzer.should_scan_file(Path("models/esm2/fixtures/data.py")) is False

    def test_commons_excluded(self) -> None:
        analyzer = DependencyAnalyzer()
        assert (
            analyzer.should_scan_file(Path("models/commons/core/decorator.py")) is False
        )

    def test_scripts_excluded(self) -> None:
        analyzer = DependencyAnalyzer()
        assert analyzer.should_scan_file(Path("models/scripts/deploy.py")) is False

    def test_pycache_excluded(self) -> None:
        analyzer = DependencyAnalyzer()
        assert analyzer.should_scan_file(Path("models/__pycache__/cached.py")) is False


class TestImportExtraction:
    """Test extraction of commons modules from Python files."""

    def test_extracts_all_commons_import_styles(self) -> None:
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
            modules = analyzer.extract_imported_modules(temp_path)

            assert modules == {
                "models.commons.core.decorator",
                "models.commons.data.request_response",
                "models.commons.modal.deployment",
                "models.commons.model.config",
            }
            assert "torch" not in modules, "Non-commons imports should be excluded"
            assert (
                "transformers" not in modules
            ), "Non-commons imports should be excluded"
        finally:
            temp_path.unlink(missing_ok=True)


class TestModuleGranularMatching:
    """Test module-granular matching of changed commons modules to models."""

    def _build_analyzer_with_stub_imports(self) -> DependencyAnalyzer:
        """Build analyzer with stub imports using a NON-critical commons file.

        Uses models.commons.model.config instead of core.decorator because
        core/decorator.py is in CRITICAL_COMMONS_FILES which triggers ALL models
        before module matching logic runs.
        """
        analyzer = DependencyAnalyzer()
        analyzer.model_imports = {
            "esm2": {
                "models.commons.model.config",
                "models.commons.core.decorator",
            },
            "evo": {"models.commons.model.config"},
            "chai1": {"models.commons.model.config"},
        }
        return analyzer

    def test_module_change_affects_all_importers(self) -> None:
        """Any change to a module triggers all models importing from it.

        Smart mode optimizes at the module level (not symbol level): only
        models importing from the changed module are affected, rather than
        ALL models (which is what default mode does).
        """
        analyzer = self._build_analyzer_with_stub_imports()
        changed_files = ["models/commons/model/config.py"]

        affected, _ = analyzer.get_affected_models(changed_files)

        # All three import from models.commons.model.config — all affected
        assert "esm2" in affected
        assert "evo" in affected
        assert "chai1" in affected

    def test_unrelated_module_not_affected(self) -> None:
        """Models that don't import from the changed module are not affected."""
        analyzer = self._build_analyzer_with_stub_imports()
        changed_files = ["models/commons/storage/r2.py"]

        affected, _ = analyzer.get_affected_models(changed_files)

        # No model in the stub imports from models.commons.storage.r2
        assert (
            len(affected) == 0
        ), f"No stub models import from storage.r2, but got: {affected}"

    def test_specific_submodule_import_matched(self) -> None:
        """A change to a module matches models importing that exact module."""
        analyzer = DependencyAnalyzer()
        analyzer.model_imports = {
            "testmodel": {"models.commons.util.environment"},
        }
        changed_files = ["models/commons/util/environment.py"]

        affected, _ = analyzer.get_affected_models(changed_files)

        assert "testmodel" in affected

    def test_parent_module_change_affects_submodule_importers(self) -> None:
        """A change to a parent module path matches submodule importers.

        e.g. a model imports `models.commons.storage.downloads`; a change to
        the `models.commons.storage` parent is a prefix of that import path
        and should still mark the model affected (conservative).
        """
        analyzer = DependencyAnalyzer()
        analyzer.model_imports = {
            "testmodel": {"models.commons.storage.downloads"},
        }
        changed_files = ["models/commons/storage.py"]

        affected, _ = analyzer.get_affected_models(changed_files)

        assert "testmodel" in affected


class TestBuildImportMap:
    """Test building the complete import map for all models."""

    def test_import_map_has_models(self) -> None:
        analyzer = DependencyAnalyzer()
        analyzer.build_import_map()
        assert len(analyzer.model_imports) > 0, "Should find at least one model"

    def test_known_model_has_imports(self) -> None:
        analyzer = DependencyAnalyzer()
        analyzer.build_import_map()
        if "esm2" in analyzer.model_imports:
            assert (
                len(analyzer.model_imports["esm2"]) > 0
            ), "ESM2 should import from commons"


class TestCriticalFiles:
    """Test that critical files trigger all models."""

    def test_each_critical_file_triggers_all_models(self) -> None:
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

    def test_smart_analysis_tests_fewer_or_equal_models(self) -> None:
        analyzer = DependencyAnalyzer()
        analyzer.build_import_map()

        changed_files = ["models/commons/model/config.py"]

        report = analyzer.generate_comparison_report(changed_files)
        assert report["new_way"]["models_tested"] <= report["old_way"]["models_tested"]
