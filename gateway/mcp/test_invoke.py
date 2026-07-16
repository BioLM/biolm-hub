"""Edge-case tests for invoke_action — all offline (Modal is mocked, no network, no billing).

Covers the mcp-best-practice failure modes: model not deployed, Modal auth failure, timeout,
connection error, invalid input, a family-vs-variant slug, an unknown action, the model's own
structured error, plus the happy path and the gateway_url route. Also one end-to-end check that a
raised error surfaces to an MCP client as an ``isError`` result.
"""

from __future__ import annotations

from typing import Any

import modal
import pytest

from gateway.mcp.invoke import InvokeError, invoke_action
from gateway.model_discovery import get_model_mapper

MAPPER = get_model_mapper()
_VALID_ITEMS = [{"sequence": "MKTAYIAKQR"}]


class _FakeRemote:
    def __init__(self, result: Any = None, exc: BaseException | None = None) -> None:
        self._result, self._exc = result, exc

    async def aio(self, **_kwargs: Any) -> Any:
        if self._exc is not None:
            raise self._exc
        return self._result


class _FakeFn:
    def __init__(self, result: Any = None, exc: BaseException | None = None) -> None:
        self.remote = _FakeRemote(result, exc)


class _FakeInstance:
    def __init__(self, action: str, result: Any, exc: BaseException | None) -> None:
        setattr(self, action, _FakeFn(result, exc))


def _patch_modal(
    monkeypatch: pytest.MonkeyPatch,
    *,
    action: str = "encode",
    result: Any = None,
    exc: BaseException | None = None,
) -> None:
    def _from_name(_app: str, _cls: str) -> Any:
        return lambda: _FakeInstance(action, result, exc)

    monkeypatch.setattr(modal.Cls, "from_name", staticmethod(_from_name))


async def test_success_returns_model_response(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_modal(monkeypatch, result={"results": [{"sequence_index": 0}]})
    out = await invoke_action(MAPPER, "esm2-650m", "encode", _VALID_ITEMS)
    assert out["results"][0]["sequence_index"] == 0


async def test_unknown_model() -> None:
    with pytest.raises(InvokeError, match="Unknown model"):
        await invoke_action(MAPPER, "not-a-model", "encode", _VALID_ITEMS)


async def test_family_slug_lists_variants() -> None:
    with pytest.raises(InvokeError, match="model family.*Pick one.*esm2-650m"):
        await invoke_action(MAPPER, "esm2", "encode", _VALID_ITEMS)


async def test_unknown_action() -> None:
    with pytest.raises(InvokeError, match="has no action 'fold'"):
        await invoke_action(MAPPER, "esm2-650m", "fold", _VALID_ITEMS)


async def test_invalid_input_is_reported_before_dispatch() -> None:
    with pytest.raises(InvokeError, match="Invalid input"):
        await invoke_action(MAPPER, "esm2-650m", "encode", [{"not_a_field": 1}])


async def test_not_deployed(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_modal(monkeypatch, exc=modal.exception.NotFoundError("nope"))
    with pytest.raises(InvokeError, match="isn't deployed.*bh deploy esm2"):
        await invoke_action(MAPPER, "esm2-650m", "encode", _VALID_ITEMS)


async def test_auth_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_modal(monkeypatch, exc=modal.exception.AuthError("bad token"))
    with pytest.raises(InvokeError, match="authentication failed.*modal token new"):
        await invoke_action(MAPPER, "esm2-650m", "encode", _VALID_ITEMS)


async def test_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_modal(monkeypatch, exc=modal.exception.FunctionTimeoutError("slow"))
    with pytest.raises(InvokeError, match="timed out"):
        await invoke_action(MAPPER, "esm2-650m", "encode", _VALID_ITEMS)


async def test_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_modal(monkeypatch, exc=modal.exception.ConnectionError("down"))
    with pytest.raises(InvokeError, match="Couldn't reach Modal"):
        await invoke_action(MAPPER, "esm2-650m", "encode", _VALID_ITEMS)


async def test_model_structured_error_is_surfaced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_modal(
        monkeypatch,
        result={"detail": "sequence too long", "status_code": 400, "code": "BAD_SEQ"},
    )
    with pytest.raises(InvokeError, match="rejected the request: sequence too long"):
        await invoke_action(MAPPER, "esm2-650m", "encode", _VALID_ITEMS)


async def test_gateway_url_path(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    def _handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/esm2-650m/encode"
        return httpx.Response(200, json={"results": [{"sequence_index": 0}]})

    real_client = httpx.AsyncClient

    def _fake_client(**kwargs: Any) -> httpx.AsyncClient:
        kwargs.pop("timeout", None)
        return real_client(transport=httpx.MockTransport(_handler))

    monkeypatch.setattr(httpx, "AsyncClient", _fake_client)
    out = await invoke_action(
        MAPPER, "esm2-650m", "encode", _VALID_ITEMS, gateway_url="https://gw.example"
    )
    assert out["results"][0]["sequence_index"] == 0


async def test_invoke_surfaces_as_mcp_iserror() -> None:
    from mcp.shared.memory import create_connected_server_and_client_session as connect

    from gateway.mcp.server import build_mcp_server

    async with connect(build_mcp_server(MAPPER)) as client:
        await client.initialize()
        result = await client.call_tool(
            "invoke_action",
            {"slug": "not-a-model", "action": "encode", "items": _VALID_ITEMS},
        )
        assert result.isError
