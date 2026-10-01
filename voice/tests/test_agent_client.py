import subprocess
import io
import json
import socket
import threading
import time
import types
import urllib.error
import pytest
from config import Config
from agent_client import (
    RunClient, ServeClient, AgentError, make_client, SESSION_TIMEOUT_S,
    _QueuedLineStream,
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
    assert seen["cmd"] == ["/x/opencode", "run", "faca algo"]

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
    assert seen["cmd"] == ["/x/opencode", "run", "--agent", "chat", "x"]


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
    assert seen[1][1]["agent"] == "vision"
    assert "model" not in seen[1][1]
    assert sum(1 for u, _, _ in seen if u.endswith("/session")) == 1


def test_serve_see_forces_tool_less_vision_agent(monkeypatch, tmp_path):
    seen = []
    png = tmp_path / "shot.png"
    png.write_bytes(b"x")
    responses = [{"id": "s"}, {"parts": [{"type": "text", "text": "ok"}]}]
    monkeypatch.setattr("agent_client.urllib.request.urlopen",
                        _fake_transport(responses, seen))
    cfg = Config(opencode_bin="/x/opencode", timeout_s=10, agent_backend="serve",
                 server_url="http://127.0.0.1:4096", agent=None)
    assert ServeClient(cfg).see("o que tem?", str(png)) == "ok"
    assert seen[1][1]["agent"] == "vision"


def test_serve_see_agent_override(monkeypatch, tmp_path):
    seen = []
    png = tmp_path / "shot.png"
    png.write_bytes(b"x")
    responses = [{"id": "s"}, {"parts": [{"type": "text", "text": "ok"}]}]
    monkeypatch.setattr("agent_client.urllib.request.urlopen",
                        _fake_transport(responses, seen))
    cfg = Config(opencode_bin="/x/opencode", timeout_s=10, agent_backend="serve",
                 server_url="http://127.0.0.1:4096", agent=None)
    assert ServeClient(cfg).see("o que tem?", str(png), agent="outro") == "ok"
    assert seen[1][1]["agent"] == "outro"


def test_serve_see_recovers_dead_session_once(monkeypatch, tmp_path):
    seen = []
    png = tmp_path / "shot.png"
    png.write_bytes(b"x")
    items = [
        {"id": "sess-1"},
        _http_error(404),
        {"id": "sess-2"},
        {"parts": [{"type": "text", "text": "ok"}]},
    ]
    monkeypatch.setattr("agent_client.urllib.request.urlopen",
                        _sequence_transport(items, seen))
    client = ServeClient(SERVE_CFG)
    assert client.see("o que tem?", str(png)) == "ok"
    assert [u for u, _, _ in seen] == [
        "http://127.0.0.1:4096/session",
        "http://127.0.0.1:4096/session/sess-1/message",
        "http://127.0.0.1:4096/session",
        "http://127.0.0.1:4096/session/sess-2/message",
    ]
    assert client._session_id == "sess-2"
    assert seen[1][1]["agent"] == "vision"
    assert seen[3][1]["agent"] == "vision"


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


def _sse(*objs):
    return io.BytesIO(
        "".join("data: " + json.dumps(o) + "\n\n" for o in objs).encode()
    )


def _stream_cfg():
    return Config(opencode_bin="/x/o", timeout_s=10, agent="chat")


def _part(pid, text, sid="S"):
    return {"type": "message.part.updated",
            "properties": {"part": {"id": pid, "type": "text",
                                    "sessionID": sid, "text": text}}}


def _msg(mid, role, sid="S"):
    return {"type": "message.updated",
            "properties": {"info": {"id": mid, "role": role, "sessionID": sid}}}


def test_consume_events_cumulative_text_emits_deltas():
    client = ServeClient(_stream_cfg())
    deltas = []
    stream = _sse(_part("p1", "Olá"), _part("p1", "Olá, tudo"),
                  {"type": "session.idle", "properties": {"sessionID": "S"}})
    text = client._consume_events(stream, "S", deltas.append, None, 10)
    assert deltas == ["Olá", ", tudo"]
    assert text == "Olá, tudo"


def test_consume_events_ignores_other_sessions():
    client = ServeClient(_stream_cfg())
    deltas = []
    stream = _sse(_part("p1", "outro", sid="X"),
                  _part("p2", "meu", sid="S"),
                  {"type": "session.idle", "properties": {"sessionID": "S"}})
    client._consume_events(stream, "S", deltas.append, None, 10)
    assert deltas == ["meu"]


def test_consume_events_empty_raises():
    client = ServeClient(_stream_cfg())
    stream = _sse({"type": "session.idle", "properties": {"sessionID": "S"}})
    try:
        client._consume_events(stream, "S", lambda d: None, None, 10)
        assert False, "deveria levantar"
    except AgentError:
        pass


def test_consume_events_skips_user_prompt_echo():
    client = ServeClient(_stream_cfg())
    deltas = []
    stream = _sse(
        _msg("m-user", "user"),
        {"type": "message.part.updated",
         "properties": {"part": {"id": "pu", "type": "text", "sessionID": "S",
                                 "messageID": "m-user",
                                 "text": "pergunta do usuario"}}},
        _msg("m-asst", "assistant"),
        {"type": "message.part.updated",
         "properties": {"part": {"id": "pa", "type": "text", "sessionID": "S",
                                 "messageID": "m-asst", "text": "resposta"}}},
        {"type": "session.idle", "properties": {"sessionID": "S"}},
    )
    text = client._consume_events(stream, "S", deltas.append, None, 10)
    assert deltas == ["resposta"]
    assert text == "resposta"


class _TimeoutThenLines:
    """Stream falso: 1a leitura levanta socket.timeout, depois entrega linhas.

    Expoe um fd real (socketpair vazio) para reproduzir a regressao: com o
    gate por `select` no fd, o loop giraria em `on_idle` sem chamar
    `readline` e nunca consumiria as linhas ja disponiveis.
    """

    def __init__(self, lines):
        self._lines = list(lines)
        self._first = True
        self._peer, self._sock = socket.socketpair()

    def fileno(self):
        return self._sock.fileno()

    def readline(self):
        if self._first:
            self._first = False
            raise socket.timeout("silencio")
        if self._lines:
            return self._lines.pop(0)
        return b""

    def close(self):
        self._peer.close()
        self._sock.close()


def test_consume_events_idle_timeout_then_lines():
    """socket.timeout em readline chama on_idle e o loop segue (nao gira)."""
    client = ServeClient(_stream_cfg())
    lines = [
        ("data: " + json.dumps(_part("p1", "resposta")) + "\n").encode(),
        ("data: " + json.dumps(
            {"type": "session.idle", "properties": {"sessionID": "S"}}
        ) + "\n").encode(),
    ]
    stream = _TimeoutThenLines(lines)
    idles = []
    try:
        text = client._consume_events(
            stream, "S", lambda d: None, lambda: idles.append(True),
            10, idle_s=0.05,
        )
    finally:
        stream.close()
    assert idles, "on_idle deveria disparar no timeout de leitura"
    assert text == "resposta"


def test_consume_events_coalesced_lines_are_consumed():
    """Conteudo + session.idle disponiveis de uma vez: consome e retorna."""
    client = ServeClient(_stream_cfg())
    stream = io.BytesIO(
        ("data: " + json.dumps(_part("p1", "junto")) + "\n\n"
         "data: " + json.dumps(
             {"type": "session.idle", "properties": {"sessionID": "S"}}
         ) + "\n\n").encode()
    )
    deltas = []
    text = client._consume_events(
        stream, "S", deltas.append, None, 10, idle_s=0.05
    )
    assert text == "junto"
    assert deltas == ["junto"]


def test_consume_events_session_error_raises():
    """session.error com texto parcial nao pode passar por sucesso."""
    client = ServeClient(_stream_cfg())
    deltas = []
    stream = _sse(
        _part("p1", "parcial"),
        {"type": "session.error", "properties": {"sessionID": "S"}},
    )
    with pytest.raises(AgentError):
        client._consume_events(stream, "S", deltas.append, None, 10)
    assert deltas == ["parcial"]


def test_stream_posts_async_and_returns_text(monkeypatch):
    client = ServeClient(_stream_cfg())
    monkeypatch.setattr(client, "_ensure_session", lambda timeout: "S")
    posted = {}

    def fake_post_no_content(path, payload, timeout):
        posted["path"] = path
        posted["payload"] = payload

    monkeypatch.setattr(client, "_post_no_content", fake_post_no_content)
    stream = _sse(_part("p1", "resposta"),
                  {"type": "session.idle", "properties": {"sessionID": "S"}})
    monkeypatch.setattr("urllib.request.urlopen", lambda url, timeout=None: stream)
    deltas = []
    text = client.stream("faca algo", deltas.append)
    assert posted["path"].endswith("/prompt_async")
    assert posted["payload"]["agent"] == "chat"
    assert text == "resposta"
    assert deltas == ["resposta"]


class _FakeDeadlockResp:
    """Resposta falsa cujo `readline` fica preso no lock do buffer.

    Expoe `.fp.raw._sock` (como o `HTTPResponse` real), `readline` que delega
    ao `makefile` e `close` que fecha o buffer. Com o socketpair vazio, a
    thread leitora fica genuinamente bloqueada dentro de `readline`.
    """

    def __init__(self, sock):
        self._sock = sock
        self._file = sock.makefile("rb")
        self.fp = types.SimpleNamespace(
            raw=types.SimpleNamespace(_sock=sock)
        )

    def readline(self):
        return self._file.readline()

    def close(self):
        self._file.close()


def test_close_does_not_block_on_buffer_lock():
    """Regressao: `close()` nao pode travar no lock do buffer da thread leitora.

    Antes do fix, `close()` chamava `resp.close()` com a thread leitora presa em
    `readline()`, bloqueando ate o timeout do socket (300s em prod). O fix faz
    `shutdown` no socket antes, entao `close()` retorna em milissegundos.
    """
    peer, sock = socket.socketpair()
    fake = _FakeDeadlockResp(sock)
    stream = _QueuedLineStream(fake, idle_s=0.05)
    time.sleep(0.2)  # garante a thread leitora bloqueada em readline()

    done = threading.Event()
    result = {}

    def _timed_close():
        t0 = time.monotonic()
        stream.close()
        result["elapsed"] = time.monotonic() - t0
        done.set()

    closer = threading.Thread(target=_timed_close, daemon=True)
    closer.start()
    try:
        assert done.wait(timeout=1.0), (
            "close() travou no lock do buffer (deadlock)"
        )
        assert result["elapsed"] < 1.0
        stream.close()  # idempotente
    finally:
        peer.close()



def test_run_ask_uses_project_root_cwd(monkeypatch):
    seen = {}
    def fake_run(cmd, **kw):
        seen["kw"] = kw
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    cfg = Config(opencode_bin="/x/o", timeout_s=10, project_root="/repo")
    RunClient(cfg).ask("x")
    assert seen["kw"]["cwd"] == "/repo"
