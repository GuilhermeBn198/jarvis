import subprocess
import json
import urllib.error
import pytest
from config import Config
from agent_client import (
    RunClient, ServeClient, AgentError, make_client, SESSION_TIMEOUT_S,
)

CFG = Config(opencode_bin="/x/opencode", timeout_s=10, agent_backend="run")
SERVE_CFG = Config(opencode_bin="/x/opencode", timeout_s=10,
                   agent_backend="serve",
                   server_url="http://127.0.0.1:4096")

def test_ask_returns_stdout(monkeypatch):
    seen = {}
    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="  resposta  \n", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    out = RunClient(CFG).ask("faca algo")
    assert out == "resposta"
    assert seen["cmd"] == ["/x/opencode", "run", "--pure", "faca algo"]

def test_empty_task_raises():
    with pytest.raises(AgentError):
        RunClient(CFG).ask("   ")

def test_missing_binary_raises(monkeypatch):
    def fake_run(*a, **k):
        raise FileNotFoundError()
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(AgentError) as exc:
        RunClient(CFG).ask("x")
    assert "nao encontrado" in str(exc.value)

def test_not_executable_binary_raises(monkeypatch):
    def fake_run(*a, **k):
        raise PermissionError()
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(AgentError) as exc:
        RunClient(CFG).ask("x")
    assert "executavel" in str(exc.value)

def test_generic_oserror_raises(monkeypatch):
    def fake_run(*a, **k):
        raise OSError("boom")
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(AgentError) as exc:
        RunClient(CFG).ask("x")
    assert "falha ao executar" in str(exc.value)

def test_empty_stdout_raises(monkeypatch):
    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(AgentError):
        RunClient(CFG).ask("x")

def test_timeout_raises(monkeypatch):
    def fake_run(*a, **k):
        raise subprocess.TimeoutExpired("cmd", 1)
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(AgentError):
        RunClient(CFG).ask("x")

def test_nonzero_exit_raises(monkeypatch):
    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 2, stdout="", stderr="boom")
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(AgentError):
        RunClient(CFG).ask("x")


class _Resp:
    def __init__(self, payload):
        self._raw = json.dumps(payload).encode("utf-8")
    def read(self):
        return self._raw
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


def _fake_transport(responses, seen):
    def urlopen(req, timeout=None):
        seen.append((req.full_url, json.loads(req.data.decode("utf-8")), timeout))
        return _Resp(responses.pop(0))
    return urlopen


def test_serve_creates_session_once_and_extracts_text(monkeypatch):
    seen = []
    responses = [
        {"id": "sess-1"},
        {"parts": [{"type": "text", "text": "ola "},
                   {"type": "tool", "text": "ignora"},
                   {"type": "text", "text": "mundo"}]},
        {"parts": [{"type": "text", "text": "de novo"}]},
    ]
    monkeypatch.setattr("agent_client.urllib.request.urlopen",
                        _fake_transport(responses, seen))
    client = ServeClient(SERVE_CFG)
    assert client.ask("pergunta 1") == "ola mundo"
    assert client.ask("pergunta 2") == "de novo"
    assert seen[0] == ("http://127.0.0.1:4096/session", {}, SERVE_CFG.timeout_s)
    assert seen[1] == (
        "http://127.0.0.1:4096/session/sess-1/message",
        {"parts": [{"type": "text", "text": "pergunta 1"}]},
        SERVE_CFG.timeout_s,
    )
    assert seen[2][0] == "http://127.0.0.1:4096/session/sess-1/message"
    assert sum(1 for u, _, _ in seen if u.endswith("/session")) == 1


def test_serve_empty_task_raises_without_http(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("nao deveria chamar HTTP")
    monkeypatch.setattr("agent_client.urllib.request.urlopen", boom)
    with pytest.raises(AgentError):
        ServeClient(SERVE_CFG).ask("   ")


def test_serve_empty_parts_raises(monkeypatch):
    seen = []
    responses = [{"id": "s"}, {"parts": []}]
    monkeypatch.setattr("agent_client.urllib.request.urlopen",
                        _fake_transport(responses, seen))
    with pytest.raises(AgentError) as exc:
        ServeClient(SERVE_CFG).ask("x")
    assert "nao retornou resposta" in str(exc.value)


def test_serve_http_error_raises(monkeypatch):
    def boom(req, timeout=None):
        raise urllib.error.URLError("recusado")
    monkeypatch.setattr("agent_client.urllib.request.urlopen", boom)
    with pytest.raises(AgentError):
        ServeClient(SERVE_CFG).ask("x")


def test_make_client_picks_backend():
    assert isinstance(make_client(CFG), RunClient)
    assert isinstance(make_client(SERVE_CFG), ServeClient)
    assert isinstance(
        make_client(Config(opencode_bin="/x/o", timeout_s=10)), ServeClient
    )


def _http_error(code):
    return urllib.error.HTTPError(
        "http://127.0.0.1:4096/session/x/message", code, "gone", {}, None
    )


def _sequence_transport(items, seen):
    def urlopen(req, timeout=None):
        seen.append((req.full_url, json.loads(req.data.decode("utf-8")), timeout))
        item = items.pop(0)
        if isinstance(item, Exception):
            raise item
        return _Resp(item)
    return urlopen


def test_serve_recovers_dead_session_once(monkeypatch):
    seen = []
    items = [
        {"id": "sess-1"},
        _http_error(404),
        {"id": "sess-2"},
        {"parts": [{"type": "text", "text": "ok"}]},
    ]
    monkeypatch.setattr("agent_client.urllib.request.urlopen",
                        _sequence_transport(items, seen))
    client = ServeClient(SERVE_CFG)
    assert client.ask("pergunta") == "ok"
    assert [u for u, _, _ in seen] == [
        "http://127.0.0.1:4096/session",
        "http://127.0.0.1:4096/session/sess-1/message",
        "http://127.0.0.1:4096/session",
        "http://127.0.0.1:4096/session/sess-2/message",
    ]
    assert client._session_id == "sess-2"


def test_serve_second_dead_session_raises(monkeypatch):
    seen = []
    items = [
        {"id": "sess-1"},
        _http_error(410),
        {"id": "sess-2"},
        _http_error(404),
    ]
    monkeypatch.setattr("agent_client.urllib.request.urlopen",
                        _sequence_transport(items, seen))
    with pytest.raises(AgentError):
        ServeClient(SERVE_CFG).ask("pergunta")


def test_serve_non_stale_http_error_not_retried(monkeypatch):
    seen = []
    items = [{"id": "sess-1"}, _http_error(500)]
    monkeypatch.setattr("agent_client.urllib.request.urlopen",
                        _sequence_transport(items, seen))
    with pytest.raises(AgentError):
        ServeClient(SERVE_CFG).ask("pergunta")
    assert len(seen) == 2


def test_serve_non_dict_json_raises(monkeypatch):
    seen = []
    monkeypatch.setattr("agent_client.urllib.request.urlopen",
                        _fake_transport([["nao", "dict"]], seen))
    with pytest.raises(AgentError) as exc:
        ServeClient(SERVE_CFG).ask("x")
    assert "objeto JSON" in str(exc.value)


def test_serve_session_post_uses_short_timeout(monkeypatch):
    seen = []
    responses = [{"id": "s"}, {"parts": [{"type": "text", "text": "ok"}]}]
    monkeypatch.setattr("agent_client.urllib.request.urlopen",
                        _fake_transport(responses, seen))
    cfg = Config(opencode_bin="/x/opencode", timeout_s=300,
                 server_url="http://127.0.0.1:4096")
    assert ServeClient(cfg).ask("x") == "ok"
    assert seen[0][2] == SESSION_TIMEOUT_S
    assert seen[1][2] == 300

