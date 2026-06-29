"""Modal-free unit tests for the anonymous public-HTTP weights read path.

The HTTP session is monkeypatched, so these run with no network, R2, or Modal.
"""

import json

import requests

from models.commons.storage import r2_http
from models.commons.storage.r2 import r2_credentials_present
from models.commons.storage.r2_utils import R2Utils

PREFIX = "model-store/esm2/v1"
PUBLIC_URL = "https://pub-test.r2.dev"


class _FakeResp:
    def __init__(self, status_code=200, body=b""):
        self.status_code = status_code
        self._body = body
        self.content = body
        self.closed = False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i : i + chunk_size]

    def close(self):
        self.closed = True


class _FakeSession:
    """Maps URL-suffix -> _FakeResp; anything unmatched is a 404. Records GETs."""

    def __init__(self, responses):
        self.responses = responses
        self.fetched: list[str] = []
        self.closed = False

    def get(self, url, stream=True, timeout=None):
        self.fetched.append(url)
        for suffix, resp in self.responses.items():
            if url.endswith(suffix):
                return resp
        return _FakeResp(404)

    def mount(self, *a, **k):
        pass

    def close(self):
        self.closed = True


def _install(monkeypatch, responses) -> _FakeSession:
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


def test_restore_hit_downloads_all_files(monkeypatch, tmp_path):
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


def test_restore_miss_when_no_completion_marker(monkeypatch, tmp_path):
    # Marker 404 => cache miss, nothing downloaded, caller falls back to source.
    _install(monkeypatch, {f"/{R2Utils.MANIFEST_FILE}": _FakeResp(200, _manifest({}))})
    assert r2_http.restore_weights_via_http(tmp_path, PREFIX, PUBLIC_URL) is False
    assert not list(tmp_path.iterdir())


def test_restore_miss_when_no_manifest(monkeypatch, tmp_path):
    # Marker present but no manifest => cannot enumerate over HTTP => miss.
    _install(monkeypatch, {f"/{R2Utils.COMPLETION_MARKER}": _FakeResp(200, b"{}")})
    assert r2_http.restore_weights_via_http(tmp_path, PREFIX, PUBLIC_URL) is False


def test_restore_skips_files_already_present_at_right_size(monkeypatch, tmp_path):
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


def test_restore_redownloads_when_local_size_mismatches(monkeypatch, tmp_path):
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


def test_restore_creates_nested_subdirectories(monkeypatch, tmp_path):
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


def test_restore_fails_when_manifested_file_missing(monkeypatch, tmp_path):
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


def test_restore_handles_non_dict_manifest_meta(monkeypatch, tmp_path):
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


def test_restore_refuses_path_traversal_keys(monkeypatch, tmp_path):
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


def test_object_url_encodes_special_characters():
    url = r2_http._object_url(
        "https://pub-test.r2.dev/", "model-store/x/v1/", "weird name#.bin"
    )
    assert url == "https://pub-test.r2.dev/model-store/x/v1/weird%20name%23.bin"


def test_credentials_present_reflects_env(monkeypatch):
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    assert r2_credentials_present() is False

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "k")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s")
    assert r2_credentials_present() is True

    # Half-configured (only the id) is not "present".
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    assert r2_credentials_present() is False
