"""CI guard for config-driven gateway discovery.

The gateway routes to each model's Modal container class by reading
``ModelFamily.modal_class_name`` from that model's ``config.py`` (no runtime
source-scanning). This guard keeps that declared name honest: for every model
it asserts that ``modal_class_name`` is set **and** names a class actually
decorated with ``@biolm_model_class`` in the model's ``app.py``.

It uses AST parsing (at test time, not runtime) so it never imports the heavy
ML ``app.py`` modules — a rename that breaks routing fails loudly here in CI
instead of silently 404-ing in production. Pytest-collectable with no Modal/R2.
"""

import ast
import importlib.util
from pathlib import Path
from typing import Optional

import pytest

from models.commons.model.config import ModelFamily, biolm_model_class

MODELS_DIR = Path(__file__).parent.parent / "models"


def _load_model_family(model_name: str) -> Optional[ModelFamily]:
    """Import <model>/config.py and return its MODEL_FAMILY (light import: no ML deps)."""
    config_path = MODELS_DIR / model_name / "config.py"
    spec = importlib.util.spec_from_file_location(
        f"models.{model_name}.config", str(config_path)
    )
    if not spec or not spec.loader:  # pragma: no cover - defensive
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    family = getattr(module, "MODEL_FAMILY", None)
    return family if isinstance(family, ModelFamily) else None


def _model_dirs() -> list[str]:
    """Names of model dirs that ship both a config.py and an app.py."""
    dirs = []
    for d in sorted(MODELS_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith(("_", ".")) or d.name == "commons":
            continue
        if (d / "config.py").exists() and (d / "app.py").exists():
            dirs.append(d.name)
    return dirs


def _decorator_name(dec: ast.expr) -> str | None:
    """Resolve a decorator node to its bare name (handles ``@x``, ``@a.x``, ``@x(...)``)."""
    if isinstance(dec, ast.Call):
        dec = dec.func
    if isinstance(dec, ast.Name):
        return dec.id
    if isinstance(dec, ast.Attribute):
        return dec.attr
    return None


def _biolm_model_classes(model_name: str) -> set[str]:
    """Names of classes decorated with @biolm_model_class in <model>/app.py.

    AST-only — does not import the module, so it works without the model's ML
    dependencies installed.
    """
    app_path = MODELS_DIR / model_name / "app.py"
    tree = ast.parse(app_path.read_text())
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        decs = {_decorator_name(d) for d in node.decorator_list}
        if biolm_model_class.__name__ in decs:
            found.add(node.name)
    return found


def _action_methods(model_name: str, class_name: str) -> set[str]:
    """Names of @modal_endpoint-decorated methods on ``class_name`` in app.py.

    These are the model's public action endpoints; the gateway registers one
    route per config action and resolves it via ``getattr(instance, action)``,
    so each config action must be backed by such a method.
    """
    app_path = MODELS_DIR / model_name / "app.py"
    tree = ast.parse(app_path.read_text())
    methods: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for item in node.body:
            if not isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if any(_decorator_name(d) == "modal_endpoint" for d in item.decorator_list):
                methods.add(item.name)
    return methods


@pytest.mark.parametrize("model_name", _model_dirs())
def test_modal_class_name_resolves(model_name: str):
    family = _load_model_family(model_name)
    assert isinstance(
        family, ModelFamily
    ), f"{model_name}/config.py does not define a MODEL_FAMILY ModelFamily."

    assert family.modal_class_name, (
        f"{model_name}: ModelFamily.modal_class_name is not set — "
        "the gateway cannot route to this model."
    )

    decorated = _biolm_model_classes(model_name)
    assert family.modal_class_name in decorated, (
        f"{model_name}: modal_class_name='{family.modal_class_name}' does not match "
        f"any @biolm_model_class class in app.py (found: {sorted(decorated) or 'none'})."
    )


@pytest.mark.parametrize("model_name", _model_dirs())
def test_config_actions_have_endpoint_methods(model_name: str):
    """Every action the gateway will route must be backed by a model method.

    The gateway registers a route per ``config.action_schemas`` entry and calls
    ``getattr(model_instance, action)`` at request time. A config action with no
    matching ``@modal_endpoint`` method would register a route that 500s on call.
    """
    family = _load_model_family(model_name)
    assert isinstance(family, ModelFamily) and family.modal_class_name

    config_actions = {str(a.name) for a in family.action_schemas}
    endpoint_methods = _action_methods(model_name, family.modal_class_name)
    missing = config_actions - endpoint_methods
    assert not missing, (
        f"{model_name}: config declares action(s) {sorted(missing)} with no matching "
        f"@modal_endpoint method on {family.modal_class_name} "
        f"(methods found: {sorted(endpoint_methods) or 'none'})."
    )
