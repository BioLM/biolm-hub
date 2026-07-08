"""
Tests for cli/deploy.py — the deploy command, focused on ``bh deploy --all``.

These cover the *planning/selection* logic (no Modal needed):
- scope selection (default variant vs --all-variants),
- --only / --exclude / --cpu-only filtering and unknown-slug validation,
- the CPU/GPU breakdown string,
- the mutual-exclusion / batch-flag argument errors,
- --dry-run output (plan + notices, deploys nothing),
- the default-variants-only notice wording (before and after),
- continue-on-error execution + exit codes,
- --skip-deployed partitioning.

The actual Modal deploy subprocess (``_run_forced_deploy``) and the
credential-less probe are patched out; nothing here talks to Modal.
"""

import subprocess
from collections.abc import Callable
from io import StringIO
from typing import NoReturn, Optional
from unittest.mock import MagicMock

import pytest
import typer
from pydantic import BaseModel
from rich.console import Console
from typer.testing import CliRunner

from cli import deploy
from cli.main import app
from models.commons.model.config import ActionSchemaMap, ModelFamily, ResolvedVariant
from models.commons.model.schema import ModalGPU, ModalResourceSpec, ModelActions
from models.commons.model.tag import (
    Architecture,
    InputModality,
    ModelTags,
    OutputModality,
    Task,
)

runner = CliRunner()

# CliRunner pipes stdout, so Rich falls back to an 80-col width and wraps long
# panel lines. A wide terminal keeps our asserted substrings on one line.
WIDE = {"COLUMNS": "200"}


# ---------------------------------------------------------------------------
# Helpers — build lightweight but real ModelFamily / variant objects
# ---------------------------------------------------------------------------


class _Req(BaseModel):
    pass


class _Res(BaseModel):
    pass


def _cpu_spec() -> ModalResourceSpec:
    return ModalResourceSpec(cpu=2.0, memory=4096)


def _gpu_spec(gpu: ModalGPU, count: Optional[int] = None) -> ModalResourceSpec:
    return ModalResourceSpec(gpu=gpu, gpu_count=count)


def _make_family(
    base_slug: str,
    variant_axes: dict[str, list[str]],
    resource_function: Callable[[dict[str, str]], ModalResourceSpec],
) -> ModelFamily:
    """A minimal, valid ModelFamily exercising the real resolved_variants engine."""
    return ModelFamily(
        base_model_slug=base_slug,
        display_name=base_slug.upper(),
        modal_class_name=f"{base_slug.title()}Model",
        tags=ModelTags(
            input_modality=[InputModality.SEQUENCE],
            task=[Task.EMBEDDING],
            output_modality=[OutputModality.EMBEDDING],
            architecture=[Architecture.TRANSFORMER],
        ),
        action_schemas=[
            ActionSchemaMap(
                name=ModelActions.ENCODE,
                request_schema=_Req,
                response_schema=_Res,
            )
        ],
        variant_axes=variant_axes,
        resource_function=resource_function,
    )


def _multi_variant_family() -> ModelFamily:
    """Two sizes: default (8m) on CPU, 650m on a T4 GPU."""

    def resource(cfg: dict[str, str]) -> ModalResourceSpec:
        return _cpu_spec() if cfg["MODEL_SIZE"] == "8m" else _gpu_spec(ModalGPU.T4)

    return _make_family("esm2", {"MODEL_SIZE": ["8m", "650m"]}, resource)


def _gpu_default_family() -> ModelFamily:
    """Single variant that runs on an A100 (a GPU-only model)."""
    return _make_family("folder", {}, lambda cfg: _gpu_spec(ModalGPU.A100_40GB))


def _capture_console() -> tuple[Console, StringIO]:
    buf = StringIO()
    return Console(file=buf, width=200), buf


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_parse_slug_csv() -> None:
    assert deploy._parse_slug_csv(None) == []
    assert deploy._parse_slug_csv("") == []
    assert deploy._parse_slug_csv("esm2, esmc ,,") == ["esm2", "esmc"]


def test_accelerator_label() -> None:
    assert deploy._accelerator_label(_cpu_spec()) == "CPU"
    assert deploy._accelerator_label(_gpu_spec(ModalGPU.T4)) == "T4"
    assert deploy._accelerator_label(_gpu_spec(ModalGPU.A100_40GB)) == "A100"
    assert deploy._accelerator_label(_gpu_spec(ModalGPU.T4, 2)) == "T4×2"


def test_gpu_breakdown() -> None:
    plan = [
        deploy.PlannedVariant("a", _mk_variant("a", _cpu_spec())),
        deploy.PlannedVariant("b", _mk_variant("b", _cpu_spec())),
        deploy.PlannedVariant("c", _mk_variant("c", _gpu_spec(ModalGPU.T4))),
        deploy.PlannedVariant("d", _mk_variant("d", _gpu_spec(ModalGPU.T4))),
        deploy.PlannedVariant("e", _mk_variant("e", _gpu_spec(ModalGPU.A100_40GB))),
    ]
    assert deploy._gpu_breakdown(plan) == "2 CPU, 3 GPU: 1×A100, 2×T4"


def test_gpu_breakdown_all_cpu() -> None:
    plan = [deploy.PlannedVariant("a", _mk_variant("a", _cpu_spec()))]
    assert deploy._gpu_breakdown(plan) == "1 CPU, 0 GPU"


def _mk_variant(app_name: str, spec: ModalResourceSpec) -> ResolvedVariant:
    return ResolvedVariant(
        name=app_name,
        modal_app_name=app_name,
        public_endpoint_slug=app_name,
        public_display_name=app_name,
        env_vars={},
        modal_resource_spec=spec,
    )


# ---------------------------------------------------------------------------
# Plan building — scope + filters
# ---------------------------------------------------------------------------


def test_build_plan_default_is_single_variant_per_model() -> None:
    families = [("esm2", _multi_variant_family())]
    plan = deploy._build_plan(families, all_variants=False, cpu_only=False)
    assert len(plan) == 1
    assert plan[0].model_name == "esm2"
    # The default is the first-declared (8m, CPU).
    assert plan[0].variant.env_vars == {"MODEL_SIZE": "8m"}


def test_build_plan_all_variants_expands_family() -> None:
    families = [("esm2", _multi_variant_family())]
    plan = deploy._build_plan(families, all_variants=True, cpu_only=False)
    assert len(plan) == 2
    assert {p.variant.env_vars["MODEL_SIZE"] for p in plan} == {"8m", "650m"}


def test_build_plan_cpu_only_drops_gpu_variants() -> None:
    families = [("esm2", _multi_variant_family())]
    plan = deploy._build_plan(families, all_variants=True, cpu_only=True)
    assert len(plan) == 1
    assert plan[0].variant.env_vars == {"MODEL_SIZE": "8m"}


def test_build_plan_cpu_only_excludes_gpu_default_model() -> None:
    families = [("folder", _gpu_default_family())]
    # The only (default) variant is GPU, so cpu-only yields nothing.
    plan = deploy._build_plan(families, all_variants=False, cpu_only=True)
    assert plan == []


# ---------------------------------------------------------------------------
# --only / --exclude resolution + validation
# ---------------------------------------------------------------------------


def _patch_discovery(
    monkeypatch: pytest.MonkeyPatch,
    names: list[str],
    family_factory: Optional[Callable[[str], ModelFamily]] = None,
) -> None:
    monkeypatch.setattr(deploy, "_discover_model_names", lambda: list(names))
    factory: Callable[[str], ModelFamily] = family_factory or (
        lambda name: _make_family(name, {}, lambda cfg: _cpu_spec())
    )
    monkeypatch.setattr(deploy, "get_model_family", factory)


def test_only_and_exclude_filtering(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_discovery(monkeypatch, ["a", "b", "c"])
    families = deploy._load_selected_families(only="a,b", exclude="b")
    assert [name for name, _ in families] == ["a"]


def test_unknown_slug_aborts(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_discovery(monkeypatch, ["esm2", "esmc"])
    with pytest.raises(typer.Exit):
        deploy._load_selected_families(only="esm2,bogus", exclude=None)


# ---------------------------------------------------------------------------
# Notice wording (before / after; default vs all-variants)
# ---------------------------------------------------------------------------


def test_default_variant_notice_before(monkeypatch: pytest.MonkeyPatch) -> None:
    console, buf = _capture_console()
    monkeypatch.setattr(deploy, "console", console)
    console.print(deploy._variant_scope_notice(all_variants=False, after=False))
    out = buf.getvalue()
    assert "DEFAULT" in out
    assert "cheapest" in out
    assert "will be deployed" in out
    assert "NOT every variant" in out
    assert "bh deploy --all --all-variants" in out


def test_default_variant_notice_after(monkeypatch: pytest.MonkeyPatch) -> None:
    console, buf = _capture_console()
    monkeypatch.setattr(deploy, "console", console)
    console.print(deploy._variant_scope_notice(all_variants=False, after=True))
    out = buf.getvalue()
    assert "was deployed" in out
    assert "bh deploy --all --all-variants" in out


def test_all_variants_notice(monkeypatch: pytest.MonkeyPatch) -> None:
    console, buf = _capture_console()
    monkeypatch.setattr(deploy, "console", console)
    console.print(deploy._variant_scope_notice(all_variants=True, after=False))
    out = buf.getvalue()
    assert "ALL variants of every model" in out


# ---------------------------------------------------------------------------
# Argument validation (mutual exclusion + batch-only flags)
# ---------------------------------------------------------------------------


def test_all_with_positional_model_errors() -> None:
    result = runner.invoke(app, ["deploy", "--all", "esm2"], env=WIDE)
    assert result.exit_code != 0
    assert "Cannot combine --all" in result.output


def test_no_model_and_no_all_errors() -> None:
    result = runner.invoke(app, ["deploy"], env=WIDE)
    assert result.exit_code != 0
    assert "Provide at least one MODEL" in result.output


def test_variant_with_all_errors() -> None:
    result = runner.invoke(
        app, ["deploy", "--all", "--variant", "MODEL_SIZE=8m"], env=WIDE
    )
    assert result.exit_code != 0
    assert "--variant" in result.output


def test_batch_flag_without_all_errors() -> None:
    result = runner.invoke(app, ["deploy", "esm2", "--cpu-only"], env=WIDE)
    assert result.exit_code != 0
    assert "--cpu-only only applies with --all" in result.output


# ---------------------------------------------------------------------------
# --dry-run (deploys nothing; emits the plan + notices)
# ---------------------------------------------------------------------------


def test_dry_run_emits_default_notice_and_deploys_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_discovery(monkeypatch, ["esm2"], lambda name: _multi_variant_family())
    no_deploy = MagicMock(side_effect=AssertionError("must not deploy in dry-run"))
    monkeypatch.setattr(deploy, "_execute_plan", no_deploy)

    result = runner.invoke(app, ["deploy", "--all", "--dry-run"], env=WIDE)

    assert result.exit_code == 0
    assert "Deployment plan" in result.output
    assert "DEFAULT" in result.output
    assert "bh deploy --all --all-variants" in result.output
    no_deploy.assert_not_called()


def test_dry_run_all_variants_notice(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_discovery(monkeypatch, ["esm2"], lambda name: _multi_variant_family())
    result = runner.invoke(
        app, ["deploy", "--all", "--all-variants", "--dry-run"], env=WIDE
    )
    assert result.exit_code == 0
    assert "ALL variants of every model" in result.output
    # Both variants should appear in the plan.
    assert "esm2-8m" in result.output
    assert "esm2-650m" in result.output


def test_dry_run_only_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    families = {
        "esm2": _multi_variant_family(),
        "folder": _gpu_default_family(),
    }
    _patch_discovery(monkeypatch, ["esm2", "folder"], lambda name: families[name])
    result = runner.invoke(
        app, ["deploy", "--all", "--only", "esm2", "--dry-run"], env=WIDE
    )
    assert result.exit_code == 0
    assert "esm2" in result.output
    assert "folder" not in result.output


# ---------------------------------------------------------------------------
# Execution: confirm gate, continue-on-error, exit codes, skip-deployed
# ---------------------------------------------------------------------------


def test_confirm_abort_deploys_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_discovery(monkeypatch, ["esm2"], lambda name: _multi_variant_family())
    monkeypatch.setattr(deploy, "_maybe_enable_credential_less", lambda: None)
    no_deploy = MagicMock(side_effect=AssertionError("must not deploy when aborted"))
    monkeypatch.setattr(deploy, "_execute_plan", no_deploy)

    result = runner.invoke(app, ["deploy", "--all"], input="n\n", env=WIDE)

    assert result.exit_code == 1
    assert "Aborted" in result.output
    no_deploy.assert_not_called()


def test_all_run_success(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_discovery(monkeypatch, ["esm2"], lambda name: _multi_variant_family())
    monkeypatch.setattr(deploy, "_maybe_enable_credential_less", lambda: None)
    monkeypatch.setattr(deploy, "_run_forced_deploy", lambda n, e: (True, "", ""))

    result = runner.invoke(app, ["deploy", "--all", "--yes"], env=WIDE)

    assert result.exit_code == 0
    assert "deployed esm2-8m" in result.output
    # The after-notice reminder is still present.
    assert "bh deploy --all --all-variants" in result.output


def test_continue_on_error_reports_failures_and_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_discovery(monkeypatch, ["esm2"], lambda name: _multi_variant_family())
    monkeypatch.setattr(deploy, "_maybe_enable_credential_less", lambda: None)
    monkeypatch.setattr(
        deploy, "_run_forced_deploy", lambda n, e: (False, "", "boom: weights missing")
    )

    result = runner.invoke(
        app, ["deploy", "--all", "--all-variants", "--yes"], env=WIDE
    )

    assert result.exit_code == 1
    assert "failed esm2-8m" in result.output
    assert "boom" in result.output
    # Both variants were attempted (continue-on-error), not just the first.
    assert "esm2-650m" in result.output


def test_skip_deployed_partitions_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_discovery(monkeypatch, ["esm2"], lambda name: _multi_variant_family())
    monkeypatch.setattr(
        "gateway.catalog.deployment_status.get_deployed_app_names",
        lambda environment=None: {"esm2-8m"},
    )
    result = runner.invoke(
        app,
        ["deploy", "--all", "--all-variants", "--skip-deployed", "--dry-run"],
        env=WIDE,
    )
    assert result.exit_code == 0
    assert "skip (deployed)" in result.output
    assert "Skipping 1 already-deployed" in result.output


# ---------------------------------------------------------------------------
# _run_forced_deploy behaviour (no real subprocess)
# ---------------------------------------------------------------------------


def test_run_forced_deploy_success(monkeypatch: pytest.MonkeyPatch) -> None:
    completed = MagicMock(stdout="ok", stderr="")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: completed)
    success, output, detail = deploy._run_forced_deploy("esm2", {})
    assert success is True
    assert detail == ""
    assert "ok" in output


def test_run_forced_deploy_failure_extracts_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    err = subprocess.CalledProcessError(
        returncode=1,
        cmd=["x"],
        output="line1\n",
        stderr="Traceback\nRuntimeError: nope",
    )

    def _raise(*a: object, **k: object) -> NoReturn:
        raise err

    monkeypatch.setattr(subprocess, "run", _raise)
    success, _output, detail = deploy._run_forced_deploy("esm2", {})
    assert success is False
    assert detail == "RuntimeError: nope"


def test_first_error_line() -> None:
    assert deploy._first_error_line("") == ""
    assert deploy._first_error_line("a\n\nb\n  \n") == "b"
