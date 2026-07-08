"""Modal-free unit tests for the anonymous public-HTTP weights read path.

The HTTP session is monkeypatched, so these run with no network, R2, or Modal.
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Optional

import pytest
import requests

from models.commons.storage import r2, r2_http
from models.commons.storage.r2 import r2_credentials_present
from models.commons.storage.r2_utils import R2Utils
from models.commons.util import config as cfg

PREFIX = "biolm-hub/model-weights/models/esm2/v1"
PUBLIC_URL = "https://pub-test.r2.dev"


class _FakeResp:
    def __init__(self, status_code: int = 200, body: bytes = b"") -> None:
        self.status_code = status_code
        self._body = body
        self.content = body
        self.closed = False

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")

    def iter_content(self, chunk_size: int = 1) -> Iterator[bytes]:
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i : i + chunk_size]

    def close(self) -> None:
        self.closed = True


class _FakeSession:
    """Maps URL-suffix -> _FakeResp; anything unmatched is a 404. Records GETs."""

    def __init__(self, responses: dict[str, "_FakeResp"]) -> None:
        self.responses = responses
        self.fetched: list[str] = []
        self.closed = False

    def get(
        self,
        url: str,
        stream: bool = True,
        timeout: Optional[tuple[int, int]] = None,
    ) -> "_FakeResp":
        self.fetched.append(url)
        for suffix, resp in self.responses.items():
            if url.endswith(suffix):
                return resp
        return _FakeResp(404)

    def mount(self, *a: Any, **k: Any) -> None:
        pass

    def close(self) -> None:
        self.closed = True


def _install(
    monkeypatch: pytest.MonkeyPatch, responses: dict[str, "_FakeResp"]
) -> _FakeSession:
    session = _FakeSession(responses)
    monkeypatch.setattr(r2_http, "_session", lambda: session)
    return session


def _manifest(files: dict[str, bytes]) -> bytes:
    return json.dumps(
        {
            name: {"size": len(body), "sha256": "x", "mtime": 1}
            for name, body in files.items()
        }
    ).encode("utf-8")


def test_restore_hit_downloads_all_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    files = {"config.json": b"hello", "weights.bin": b"abc"}
    session = _install(
        monkeypatch,
        {
            f"/{R2Utils.COMPLETION_MARKER}": _FakeResp(200, b"{}"),
            f"/{R2Utils.MANIFEST_FILE}": _FakeResp(200, _manifest(files)),
            "/config.json": _FakeResp(200, files["config.json"]),
            "/weights.bin": _FakeResp(200, files["weights.bin"]),
        },
    )

    assert r2_http.restore_weights_via_http(tmp_path, PREFIX, PUBLIC_URL) is True
    assert (tmp_path / "config.json").read_bytes() == b"hello"
    assert (tmp_path / "weights.bin").read_bytes() == b"abc"
    # Dotfiles must never be materialized into the model dir.
    assert not (tmp_path / R2Utils.COMPLETION_MARKER).exists()
    assert not (tmp_path / R2Utils.MANIFEST_FILE).exists()
    # The session is closed (no connection leak).
    assert session.closed is True


def test_restore_miss_when_no_completion_marker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Marker 404 => cache miss, nothing downloaded, caller falls back to source.
    _install(monkeypatch, {f"/{R2Utils.MANIFEST_FILE}": _FakeResp(200, _manifest({}))})
    assert r2_http.restore_weights_via_http(tmp_path, PREFIX, PUBLIC_URL) is False
    assert not list(tmp_path.iterdir())


def test_restore_miss_when_no_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Marker present but no manifest => cannot enumerate over HTTP => miss.
    _install(monkeypatch, {f"/{R2Utils.COMPLETION_MARKER}": _FakeResp(200, b"{}")})
    assert r2_http.restore_weights_via_http(tmp_path, PREFIX, PUBLIC_URL) is False


def test_restore_skips_files_already_present_at_right_size(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    files = {"config.json": b"hello"}
    # Pre-place config.json at the manifested size; the GET for it must NOT fire.
    (tmp_path / "config.json").write_bytes(b"hello")
    session = _install(
        monkeypatch,
        {
            f"/{R2Utils.COMPLETION_MARKER}": _FakeResp(200, b"{}"),
            f"/{R2Utils.MANIFEST_FILE}": _FakeResp(200, _manifest(files)),
            # No "/config.json" entry -> a GET for it would 404 and fail the restore.
        },
    )

    assert r2_http.restore_weights_via_http(tmp_path, PREFIX, PUBLIC_URL) is True
    assert not any(u.endswith("/config.json") for u in session.fetched)


def test_restore_redownloads_when_local_size_mismatches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    files = {"config.json": b"hello"}  # manifest size = 5
    (tmp_path / "config.json").write_bytes(b"xx")  # wrong size -> must re-fetch
    _install(
        monkeypatch,
        {
            f"/{R2Utils.COMPLETION_MARKER}": _FakeResp(200, b"{}"),
            f"/{R2Utils.MANIFEST_FILE}": _FakeResp(200, _manifest(files)),
            "/config.json": _FakeResp(200, b"hello"),
        },
    )

    assert r2_http.restore_weights_via_http(tmp_path, PREFIX, PUBLIC_URL) is True
    assert (tmp_path / "config.json").read_bytes() == b"hello"


def test_restore_creates_nested_subdirectories(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    files = {"sub/dir/w.bin": b"deep"}
    _install(
        monkeypatch,
        {
            f"/{R2Utils.COMPLETION_MARKER}": _FakeResp(200, b"{}"),
            f"/{R2Utils.MANIFEST_FILE}": _FakeResp(200, _manifest(files)),
            "/sub/dir/w.bin": _FakeResp(200, b"deep"),
        },
    )

    assert r2_http.restore_weights_via_http(tmp_path, PREFIX, PUBLIC_URL) is True
    assert (tmp_path / "sub" / "dir" / "w.bin").read_bytes() == b"deep"


def test_restore_fails_when_manifested_file_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Manifest lists a file that 404s => incomplete cache => False (not a silent hit).
    _install(
        monkeypatch,
        {
            f"/{R2Utils.COMPLETION_MARKER}": _FakeResp(200, b"{}"),
            f"/{R2Utils.MANIFEST_FILE}": _FakeResp(
                200, _manifest({"weights.bin": b"abc"})
            ),
            # no entry for /weights.bin => 404
        },
    )
    assert r2_http.restore_weights_via_http(tmp_path, PREFIX, PUBLIC_URL) is False


def test_restore_handles_non_dict_manifest_meta(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A malformed manifest value (not a dict) => no size => always GET (no skip).
    raw = json.dumps({"w.bin": None}).encode("utf-8")
    _install(
        monkeypatch,
        {
            f"/{R2Utils.COMPLETION_MARKER}": _FakeResp(200, b"{}"),
            f"/{R2Utils.MANIFEST_FILE}": _FakeResp(200, raw),
            "/w.bin": _FakeResp(200, b"data"),
        },
    )
    assert r2_http.restore_weights_via_http(tmp_path, PREFIX, PUBLIC_URL) is True
    assert (tmp_path / "w.bin").read_bytes() == b"data"


def test_restore_refuses_path_traversal_keys(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "model"
    target.mkdir()
    for bad_key in ("../escape.bin", "/abs/escape.bin"):
        _install(
            monkeypatch,
            {
                f"/{R2Utils.COMPLETION_MARKER}": _FakeResp(200, b"{}"),
                f"/{R2Utils.MANIFEST_FILE}": _FakeResp(200, _manifest({bad_key: b"x"})),
                # even if a GET were attempted, serve content — the guard must stop it
                "escape.bin": _FakeResp(200, b"x"),
            },
        )
        assert r2_http.restore_weights_via_http(target, PREFIX, PUBLIC_URL) is False
    # Nothing was written outside the target dir.
    assert not (tmp_path / "escape.bin").exists()
    assert not (tmp_path.parent / "escape.bin").exists()


def test_object_url_encodes_special_characters() -> None:
    url = r2_http._object_url(
        "https://pub-test.r2.dev/",
        "biolm-hub/model-weights/models/x/v1/",
        "weird name#.bin",
    )
    assert (
        url
        == "https://pub-test.r2.dev/biolm-hub/model-weights/models/x/v1/weird%20name%23.bin"
    )


GOLDEN_KEY = "biolm-hub/test-data/models/esm2/predict_output.json"


def test_key_url_encodes_special_characters() -> None:
    url = r2_http._key_url(
        "https://pub-test.r2.dev/",
        "biolm-hub/test-data/models/x/weird name#.json",
    )
    assert (
        url
        == "https://pub-test.r2.dev/biolm-hub/test-data/models/x/weird%20name%23.json"
    )


def test_read_json_via_http_returns_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _install(
        monkeypatch,
        {f"/{GOLDEN_KEY}": _FakeResp(200, b'{"results": [{"log_prob": -1.0}]}')},
    )
    assert r2_http.read_json_via_http(PUBLIC_URL, GOLDEN_KEY) == {
        "results": [{"log_prob": -1.0}]
    }
    # The session is closed (no connection leak) — parity with the weights path.
    assert session.closed is True


def test_read_json_via_http_404_raises_filenotfound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Nothing registered => 404 => FileNotFoundError (mirrors read_json_from_r2).
    _install(monkeypatch, {})
    with pytest.raises(FileNotFoundError):
        r2_http.read_json_via_http(PUBLIC_URL, GOLDEN_KEY)


def test_read_json_via_http_wraps_parse_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Malformed JSON body => wrapped as FileNotFoundError, not a raw JSONDecodeError.
    _install(monkeypatch, {f"/{GOLDEN_KEY}": _FakeResp(200, b"not json{")})
    with pytest.raises(FileNotFoundError):
        r2_http.read_json_via_http(PUBLIC_URL, GOLDEN_KEY)


def test_read_json_from_r2_falls_back_to_http_without_creds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No S3 creds + a public URL => read anonymously over HTTP; the S3 client must
    # never be built. This is what makes `pytest -m integration` credential-less.
    monkeypatch.setattr(r2, "r2_credentials_present", lambda: False)
    monkeypatch.setattr(cfg, "r2_public_url", PUBLIC_URL)

    def _no_client() -> object:
        raise AssertionError("get_r2_client must not run on the credential-less path")

    monkeypatch.setattr(r2, "get_r2_client", _no_client)
    _install(monkeypatch, {f"/{GOLDEN_KEY}": _FakeResp(200, b'{"ok": true}')})

    assert r2.read_json_from_r2("some-bucket", GOLDEN_KEY) == {"ok": True}


def test_read_json_from_r2_uses_s3_when_creds_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Creds present => the signed S3 path is used UNCHANGED; the HTTP fallback must
    # not run (proves the HTTP fallback leaves the credentialed read/write flow intact).
    monkeypatch.setattr(r2, "r2_credentials_present", lambda: True)

    class _Body:
        def read(self) -> bytes:
            return b'{"from": "s3"}'

    class _Client:
        def get_object(self, Bucket: str, Key: str) -> dict[str, object]:
            assert (Bucket, Key) == ("some-bucket", GOLDEN_KEY)
            return {"Body": _Body()}

    monkeypatch.setattr(r2, "get_r2_client", lambda: _Client())

    def _boom(*a: object, **k: object) -> object:
        raise AssertionError("HTTP fallback must not run when creds are present")

    monkeypatch.setattr(r2_http, "read_json_via_http", _boom)

    assert r2.read_json_from_r2("some-bucket", GOLDEN_KEY) == {"from": "s3"}


def test_credentials_present_reflects_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    assert r2_credentials_present() is False

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "k")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s")
    assert r2_credentials_present() is True

    # Half-configured (only the id) is not "present".
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    assert r2_credentials_present() is False
