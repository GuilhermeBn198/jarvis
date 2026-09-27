import json

import serve
from config import Config

CFG = Config(
    opencode_bin="/x/opencode",
    timeout_s=10,
    server_url="http://127.0.0.1:4096",
)


class _Resp:
    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


def test_is_healthy_true(monkeypatch):
    monkeypatch.setattr(
        serve.urllib.request, "urlopen", lambda url, timeout=None: _Resp(b'{"healthy": true}')
    )
    assert serve.is_healthy("http://127.0.0.1:4096") is True


def test_is_healthy_false_on_error(monkeypatch):
    def boom(url, timeout=None):
        raise OSError("recusado")
    monkeypatch.setattr(serve.urllib.request, "urlopen", boom)
    assert serve.is_healthy("http://127.0.0.1:4096") is False


def test_is_healthy_false_on_bad_json(monkeypatch):
    monkeypatch.setattr(
        serve.urllib.request, "urlopen", lambda url, timeout=None: _Resp(b"nope")
    )
    assert serve.is_healthy("http://127.0.0.1:4096") is False


def test_ensure_server_already_healthy(monkeypatch):
    monkeypatch.setattr(serve, "is_healthy", lambda url, timeout=2: True)

    def boom(*a, **k):
        raise AssertionError("nao deve subir o servidor")
    monkeypatch.setattr(serve.subprocess, "Popen", boom)
    assert serve.ensure_server(CFG) is True


def test_ensure_server_spawns_and_waits(monkeypatch, tmp_path):
    monkeypatch.setenv("SERVE_LOG", str(tmp_path / "serve.log"))
    calls = {"n": 0}

    def health(url, timeout=2):
        calls["n"] += 1
        return calls["n"] >= 2
    monkeypatch.setattr(serve, "is_healthy", health)
    spawned = {}

    def popen(cmd, **kw):
        spawned["cmd"] = cmd
        spawned["kw"] = kw
        return object()
    monkeypatch.setattr(serve.subprocess, "Popen", popen)
    assert serve.ensure_server(CFG, wait_s=5) is True
    assert spawned["cmd"] == ["/x/opencode", "serve", "--port", "4096"]
    assert spawned["kw"]["start_new_session"] is True
    assert spawned["kw"]["stdin"] == serve.subprocess.DEVNULL


def test_ensure_server_spawn_failure_returns_false(monkeypatch, tmp_path):
    monkeypatch.setenv("SERVE_LOG", str(tmp_path / "serve.log"))
    monkeypatch.setattr(serve, "is_healthy", lambda url, timeout=2: False)

    def popen(*a, **k):
        raise OSError("binario ausente")
    monkeypatch.setattr(serve.subprocess, "Popen", popen)
    assert serve.ensure_server(CFG, wait_s=1) is False


def test_ensure_server_never_healthy_returns_false(monkeypatch, tmp_path):
    monkeypatch.setenv("SERVE_LOG", str(tmp_path / "serve.log"))
    monkeypatch.setattr(serve, "is_healthy", lambda url, timeout=2: False)
    monkeypatch.setattr(serve.subprocess, "Popen", lambda *a, **k: object())
    monkeypatch.setattr(serve.time, "sleep", lambda s: None)
    ticks = iter([0.0, 0.0, 10.0])
    monkeypatch.setattr(serve.time, "monotonic", lambda: next(ticks))
    assert serve.ensure_server(CFG, wait_s=5) is False


def test_spawn_handles_log_without_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SERVE_LOG", "serve.log")
    monkeypatch.setattr(serve, "is_healthy", lambda url, timeout=2: False)
    spawned = {}
    monkeypatch.setattr(
        serve.subprocess, "Popen",
        lambda cmd, **kw: spawned.update(kw) or object(),
    )
    monkeypatch.setattr(serve.time, "sleep", lambda s: None)
    ticks = iter([0.0, 10.0])
    monkeypatch.setattr(serve.time, "monotonic", lambda: next(ticks))
    assert serve.ensure_server(CFG, wait_s=1) is False
    assert spawned["stdout"] != serve.subprocess.DEVNULL


def test_ensure_server_never_raises(monkeypatch):
    def boom(url, timeout=2):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(serve, "is_healthy", boom)
    assert serve.ensure_server(CFG) is False
