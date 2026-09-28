import subprocess
import json
import urllib.error
import pytest
from config import Config
from agent_client import (
    RunClient, ServeClient, AgentError, make_client, SESSION_TIMEOUT_S,
)

CFG = Config(opencode_bin="/x/opencode", timeout_s=10, agent_backend="run",
             agent=None)
SERVE_CFG = Config(opencode_bin="/x/opencode", timeout_s=10,
                   agent_backend="serve", agent=None,
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


def test_run_client_strips_ansi_and_header(monkeypatch):
    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(
            cmd, 0, stdout="\x1b[0m\n> build \u00b7 deepseek-v4.1-flash\nresposta\x1b[0m\n",
            stderr="",
        )
    monkeypatch.setattr(subprocess, "run", fake_run)
    assert RunClient(CFG).ask("x") == "resposta"


def test_run_client_passes_agent_when_configured(monkeypatch):
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    cfg = Config(opencode_bin="/x/opencode", timeout_s=10,
                 agent_backend="run", agent="chat")
    RunClient(cfg).ask("x")
    assert seen["cmd"] == ["/x/opencode", "run", "--agent", "chat", "--pure", "x"]


def test_no_agent_flag_when_unset(monkeypatch):
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    RunClient(CFG).ask("x")
    assert "--agent" not in seen["cmd"]


def test_serve_passes_agent_when_configured(monkeypatch):
    seen = []
    responses = [{"id": "s"}, {"parts": [{"type": "text", "text": "ok"}]}]
    monkeypatch.setattr("agent_client.urllib.request.urlopen",
                        _fake_transport(responses, seen))
    cfg = Config(opencode_bin="/x/opencode", timeout_s=10, agent_backend="serve",
                 server_url="http://127.0.0.1:4096", agent="chat")
    assert ServeClient(cfg).ask("pergunta") == "ok"
    assert seen[1][1] == {
        "parts": [{"type": "text", "text": "pergunta"}],
        "agent": "chat",
    }

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


def test_serve_see_sends_image_and_model(monkeypatch, tmp_path):
    seen = []
    png = tmp_path / "shot.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    responses = [{"id": "s"}, {"parts": [{"type": "text", "text": " uma tela "}]}]
    monkeypatch.setattr("agent_client.urllib.request.urlopen",
                        _fake_transport(responses, seen))
    cfg = Config(opencode_bin="/x/opencode", timeout_s=10, agent_backend="serve",
                 server_url="http://127.0.0.1:4096", agent=None)
    out = ServeClient(cfg).see(
        " o que tem? ", str(png),
        model_id="opencode-go/deepseek-v4-flash-vision-exp",
    )
    assert out == "uma tela"
    url, payload, _ = seen[1]
    assert url == "http://127.0.0.1:4096/session/s/message"
    text_part, file_part = payload["parts"]
    assert text_part == {"type": "text", "text": "o que tem?"}
    assert file_part["type"] == "file"
    assert file_part["mime"] == "image/png"
    assert file_part["filename"] == "shot.png"
    assert file_part["url"].startswith("data:image/png;base64,")
    assert payload["model"] == {
        "providerID": "opencode-go", "modelID": "deepseek-v4-flash-vision-exp",
    }


def test_serve_see_reuses_session_and_passes_agent(monkeypatch, tmp_path):
    seen = []
    png = tmp_path / "shot.png"
    png.write_bytes(b"x")
    responses = [
        {"id": "sess-1"},
        {"parts": [{"type": "text", "text": "a"}]},
        {"parts": [{"type": "text", "text": "b"}]},
    ]
    monkeypatch.setattr("agent_client.urllib.request.urlopen",
                        _fake_transport(responses, seen))
    cfg = Config(opencode_bin="/x/opencode", timeout_s=10, agent_backend="serve",
                 server_url="http://127.0.0.1:4096", agent="chat")
    client = ServeClient(cfg)
    assert client.see("a", str(png)) == "a"
    assert client.see("b", str(png)) == "b"
    assert seen[1][1]["agent"] == "chat"
    assert "model" not in seen[1][1]
    assert sum(1 for u, _, _ in seen if u.endswith("/session")) == 1


def test_serve_see_empty_prompt_raises_without_http(monkeypatch, tmp_path):
    png = tmp_path / "shot.png"
    png.write_bytes(b"x")

    def boom(*a, **k):
        raise AssertionError("nao deveria chamar HTTP")

    monkeypatch.setattr("agent_client.urllib.request.urlopen", boom)
    with pytest.raises(AgentError):
        ServeClient(SERVE_CFG).see("   ", str(png))


def test_serve_see_missing_file_raises(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise AssertionError("nao deveria chamar HTTP")

    monkeypatch.setattr("agent_client.urllib.request.urlopen", boom)
    with pytest.raises(AgentError) as exc:
        ServeClient(SERVE_CFG).see("x", str(tmp_path / "nao_existe.png"))
    assert "imagem" in str(exc.value)


def test_serve_see_empty_reply_raises(monkeypatch, tmp_path):
    seen = []
    png = tmp_path / "shot.png"
    png.write_bytes(b"x")
    responses = [{"id": "s"}, {"parts": []}]
    monkeypatch.setattr("agent_client.urllib.request.urlopen",
                        _fake_transport(responses, seen))
    with pytest.raises(AgentError) as exc:
        ServeClient(SERVE_CFG).see("x", str(png))
    assert "nao retornou resposta" in str(exc.value)


def test_serve_see_bad_model_id_raises(monkeypatch, tmp_path):
    seen = []
    png = tmp_path / "shot.png"
    png.write_bytes(b"x")

    def boom(*a, **k):
        raise AssertionError("nao deveria chamar HTTP")

    monkeypatch.setattr("agent_client.urllib.request.urlopen", boom)
    with pytest.raises(AgentError) as exc:
        ServeClient(SERVE_CFG).see("x", str(png), model_id="sem-barra")
    assert "model_id" in str(exc.value)

