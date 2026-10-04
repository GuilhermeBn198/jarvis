# Jarvis — Indicador visual de estado (overlay/orbe) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emitir o estado do `voice_loop` por SSE e exibi-lo como um orbe sempre-no-topo no Windows (Tauri), com menu de comandos.

**Architecture:** O cérebro (WSL/Python) sobe um `StateHub` com um servidor `ThreadingHTTPServer` (só stdlib) que serve `/state` (snapshot), `/events` (SSE, snapshot no connect + transições + heartbeat) e recebe `/command` (fila `.mute/.pause/.quit`). A GUI (Tauri, webview) assina o SSE e desenha o orbe; comandos e "iniciar cérebro" fazem o caminho inverso.

**Tech Stack:** Python 3.10 (WSL, stdlib), `pytest`; Tauri v2 (template vanilla, sem framework JS), Rust, WebView2.

## Global Constraints

- **Só stdlib** em `voice/state.py` (nenhuma dependência nova).
- Contrato do hub (verbatim): `StateHub(port=8765, host="127.0.0.1")`, `set(state, detail=None)`, `snapshot() -> dict`, `subscribers() -> int`, `take_command() -> str | None`, `start()`, `stop()`.
- Estados (verbatim): `("idle","listening","transcribing","thinking","speaking","acting","error")`.
- Comandos (verbatim): `("mute","pause","quit")`.
- Cores por estado (verbatim): `idle` #64748b · `listening` #22d3ee · `transcribing` #a855f7 · `thinking` #34d399 · `speaking` #f59e0b · `acting` #f43f5e · `error` #ef4444.
- Env: `JARVIS_STATE_PORT` (default `8765`), `JARVIS_REQUIRE_GUI` (default `false`).
- Anti-órfão: com `JARVIS_REQUIRE_GUI=1`, 0 assinantes SSE por **15s** → o loop encerra.
- **O indicador nunca derruba a voz:** falha no hub vira aviso em stderr e o loop roda sem ele.
- Testes: `cd voice && . .venv/bin/activate && pytest -q`.
- Todo passo termina em commit.
- Compatibilidade: `hub=None` (default) mantém o comportamento atual e os testes existentes passando.

## File Structure

```
voice/
  state.py                    # StateHub: estado + HTTP (/state, /events, /command) + start/stop
  config.py                   # + state_port, state_require_gui
  loop.py                     # emite transições, consome comandos, anti-órfão
  tests/test_state.py         # novo
  tests/test_config.py        # + testes das novas envs
  tests/test_voice_loop.py    # + testes de emissão/comandos; ajusta lambdas existentes
gui/
  src/index.html              # orbe + handle de arrasto + rótulo + menu
  src/styles.css              # orbe por estado (cores + animações)
  src/main.js                 # EventSource + comandos + brain
  src-tauri/src/lib.rs        # comando Rust start_brain (wsl.exe)
  src-tauri/tauri.conf.json   # janela transparente/top-most, withGlobalTauri, CSP
  src-tauri/capabilities/default.json  # permissões de janela
```

---

### Task 1: Núcleo do `StateHub` (estado, snapshot, assinantes)

**Files:**
- Create: `voice/state.py`
- Create: `voice/tests/test_state.py`

**Interfaces:**
- Produces: `STATES: tuple[str, ...]`, `COMMANDS: tuple[str, ...]`, `HEARTBEAT_S: float`, `class StateHub` com `__init__(port=8765, host="127.0.0.1")`, `snapshot()`, `set(state, detail=None)`, `subscribe() -> queue.Queue`, `unsubscribe(q)`, `subscribers() -> int`, `take_command() -> str | None`, `push_command(cmd)`.

- [ ] **Step 1: Escrever o teste que falha**

```python
# voice/tests/test_state.py
import queue

import pytest

from state import COMMANDS, STATES, StateHub


def test_set_publishes_to_subscriber():
    hub = StateHub(port=0)
    q = hub.subscribe()
    hub.set("thinking", "agente")
    payload = q.get_nowait()
    assert '"state": "thinking"' in payload
    assert '"detail": "agente"' in payload


def test_snapshot_reflects_last_state():
    hub = StateHub(port=0)
    assert hub.snapshot()["state"] == "idle"
    hub.set("speaking")
    snap = hub.snapshot()
    assert snap["state"] == "speaking"
    assert "ts" in snap


def test_set_rejects_unknown_state():
    hub = StateHub(port=0)
    with pytest.raises(ValueError):
        hub.set("dormindo")


def test_subscribers_count_and_unsubscribe():
    hub = StateHub(port=0)
    q = hub.subscribe()
    assert hub.subscribers() == 1
    hub.unsubscribe(q)
    assert hub.subscribers() == 0
    hub.unsubscribe(q)  # idempotente
    assert hub.subscribers() == 0


def test_take_command_empty_is_none():
    hub = StateHub(port=0)
    assert hub.take_command() is None


def test_push_and_take_command_fifo():
    hub = StateHub(port=0)
    hub.push_command("mute")
    hub.push_command("quit")
    assert hub.take_command() == "mute"
    assert hub.take_command() == "quit"
    assert hub.take_command() is None


def test_push_command_rejects_unknown():
    hub = StateHub(port=0)
    with pytest.raises(ValueError):
        hub.push_command("explode")


def test_states_and_commands_are_exact():
    assert STATES == (
        "idle", "listening", "transcribing", "thinking",
        "speaking", "acting", "error",
    )
    assert COMMANDS == ("mute", "pause", "quit")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd voice && . .venv/bin/activate && pytest tests/test_state.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'state'`

- [ ] **Step 3: Implementar o núcleo**

```python
# voice/state.py
import json
import queue
import threading
import time

STATES = ("idle", "listening", "transcribing", "thinking", "speaking", "acting", "error")
COMMANDS = ("mute", "pause", "quit")
HEARTBEAT_S = 10.0


class StateHub:
    def __init__(self, port: int = 8765, host: str = "127.0.0.1"):
        self._host = host
        self._port = port
        self._lock = threading.Lock()
        self._state = "idle"
        self._detail: str | None = None
        self._subscribers: list[queue.Queue] = []
        self._commands: queue.Queue = queue.Queue()
        self._server = None
        self._thread: threading.Thread | None = None

    def snapshot(self) -> dict:
        with self._lock:
            return {"state": self._state, "detail": self._detail, "ts": time.time()}

    def set(self, state: str, detail: str | None = None) -> None:
        if state not in STATES:
            raise ValueError(f"estado invalido: {state}")
        with self._lock:
            self._state = state
            self._detail = detail
            subs = list(self._subscribers)
        payload = json.dumps({"state": state, "detail": detail, "ts": time.time()})
        for q in subs:
            q.put(payload)

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def subscribers(self) -> int:
        with self._lock:
            return len(self._subscribers)

    def take_command(self) -> str | None:
        try:
            return self._commands.get_nowait()
        except queue.Empty:
            return None

    def push_command(self, cmd: str) -> None:
        if cmd not in COMMANDS:
            raise ValueError(f"comando invalido: {cmd}")
        self._commands.put(cmd)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd voice && . .venv/bin/activate && pytest tests/test_state.py -q`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add voice/state.py voice/tests/test_state.py
git commit -m "feat(jarvis): StateHub - estado, snapshot e assinantes"
```

---

### Task 2: HTTP do `StateHub` (`/state`, `/events` SSE, `/command`)

**Files:**
- Modify: `voice/state.py`
- Modify: `voice/tests/test_state.py`

**Interfaces:**
- Consumes: `StateHub` da Task 1.
- Produces: `StateHub.start()`, `StateHub.stop()`, `StateHub.port` (propriedade só-leitura via `_port` após bind; usa-se `port=0` para porta efêmera em testes).

- [ ] **Step 1: Escrever os testes que falham**

Acrescente ao fim de `voice/tests/test_state.py`:

```python
import json
import time
import urllib.request


def _read_line(resp):
    return resp.readline().decode("utf-8")


def test_http_state_endpoint():
    hub = StateHub(port=0)
    hub.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{hub._port}/state", timeout=2) as r:
            assert r.status == 200
            assert json.loads(r.read())["state"] == "idle"
        hub.set("acting")
        with urllib.request.urlopen(f"http://127.0.0.1:{hub._port}/state", timeout=2) as r:
            assert json.loads(r.read())["state"] == "acting"
    finally:
        hub.stop()


def test_events_sends_snapshot_then_transitions():
    hub = StateHub(port=0)
    hub.start()
    try:
        resp = urllib.request.urlopen(
            f"http://127.0.0.1:{hub._port}/events", timeout=3
        )
        first = _read_line(resp)
        assert first.startswith("data: ")
        assert json.loads(first[6:])["state"] == "idle"
        assert _read_line(resp) == "\n"
        hub.set("listening")
        second = _read_line(resp)
        assert json.loads(second[6:])["state"] == "listening"
        resp.close()
        hub.stop()
        time.sleep(0.05)
        assert hub.subscribers() == 0
    finally:
        hub.stop()


def test_post_command_enqueues_and_validates():
    hub = StateHub(port=0)
    hub.start()
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{hub._port}/command",
            data=json.dumps({"cmd": "mute"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=2) as r:
            assert r.status == 200
        assert hub.take_command() == "mute"

        bad = urllib.request.Request(
            f"http://127.0.0.1:{hub._port}/command",
            data=json.dumps({"cmd": "explode"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(bad, timeout=2)
            assert False, "deveria dar 400"
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
    finally:
        hub.stop()


def test_start_stop_is_clean():
    hub = StateHub(port=0)
    hub.start()
    hub.start()  # idempotente
    hub.stop()
    hub.stop()  # idempotente
```

Adicione também `import urllib.error` no topo do arquivo (junto de `import urllib.request`).

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd voice && . .venv/bin/activate && pytest tests/test_state.py -q`
Expected: FAIL com `AttributeError: 'StateHub' object has no attribute 'start'`

- [ ] **Step 3: Implementar o servidor**

Acrescente ao topo de `voice/state.py`:

```python
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
```

Adicione, **antes** de `class StateHub`, a fábrica de handler:

```python
def _make_handler(hub):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _json(self, code: int, obj: dict) -> None:
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/state":
                self._json(200, hub.snapshot())
            elif self.path == "/events":
                self._events()
            else:
                self._json(404, {"error": "not found"})

        def _events(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            q = hub.subscribe()
            try:
                self.wfile.write(
                    f"data: {json.dumps(hub.snapshot())}\n\n".encode("utf-8")
                )
                self.wfile.flush()
                while True:
                    try:
                        payload = q.get(timeout=HEARTBEAT_S)
                        self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                hub.unsubscribe(q)

        def do_POST(self):
            if self.path != "/command":
                self._json(404, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                cmd = json.loads(raw.decode("utf-8")).get("cmd")
            except (ValueError, UnicodeDecodeError):
                self._json(400, {"error": "json invalido"})
                return
            if cmd not in COMMANDS:
                self._json(400, {"error": f"comando invalido: {cmd}"})
                return
            hub.push_command(cmd)
            self._json(200, {"ok": True})

    return Handler
```

Adicione os métodos na `StateHub` (após `push_command`):

```python
    def start(self) -> None:
        if self._server is not None:
            return
        server = ThreadingHTTPServer((self._host, self._port), _make_handler(self))
        server.daemon_threads = True
        self._port = server.server_address[1]
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd voice && . .venv/bin/activate && pytest tests/test_state.py -q`
Expected: PASS (12 passed)

- [ ] **Step 5: Commit**

```bash
git add voice/state.py voice/tests/test_state.py
git commit -m "feat(jarvis): StateHub - HTTP /state, SSE /events e POST /command"
```

---

### Task 3: Config (`state_port`, `state_require_gui`)

**Files:**
- Modify: `voice/config.py`
- Modify: `voice/tests/test_config.py`

**Interfaces:**
- Produces: campos `Config.state_port: int` e `Config.state_require_gui: bool`; constantes `DEFAULT_STATE_PORT`, `DEFAULT_STATE_REQUIRE_GUI`.

- [ ] **Step 1: Escrever os testes que falham**

Acrescente ao fim de `voice/tests/test_config.py`:

```python
def test_state_defaults():
    from config import DEFAULT_STATE_PORT
    cfg = load_config({})
    assert cfg.state_port == DEFAULT_STATE_PORT == 8765
    assert cfg.state_require_gui is False


def test_state_env_overrides():
    cfg = load_config({"JARVIS_STATE_PORT": "9000", "JARVIS_REQUIRE_GUI": "1"})
    assert cfg.state_port == 9000
    assert cfg.state_require_gui is True
    for truthy in ("1", "true", "TRUE", "yes", "on"):
        assert load_config({"JARVIS_REQUIRE_GUI": truthy}).state_require_gui is True
    for falsy in ("0", "false", "no", "off", ""):
        assert load_config({"JARVIS_REQUIRE_GUI": falsy}).state_require_gui is False


def test_state_port_invalid_raises():
    with pytest.raises(ValueError) as exc:
        load_config({"JARVIS_STATE_PORT": "abc"})
    assert "JARVIS_STATE_PORT" in str(exc.value)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd voice && . .venv/bin/activate && pytest tests/test_config.py -q`
Expected: FAIL com `AttributeError: 'Config' object has no attribute 'state_port'`

- [ ] **Step 3: Implementar**

Em `voice/config.py`, junto das demais constantes:

```python
DEFAULT_STATE_PORT = 8765
DEFAULT_STATE_REQUIRE_GUI = False
```

Nos campos de `Config` (após `ptt: bool = False`):

```python
    state_port: int = DEFAULT_STATE_PORT
    state_require_gui: bool = DEFAULT_STATE_REQUIRE_GUI
```

Em `load_config`, antes do `return Config(...)`:

```python
    raw_state_port = e.get("JARVIS_STATE_PORT", DEFAULT_STATE_PORT)
    try:
        state_port = int(raw_state_port)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"JARVIS_STATE_PORT deve ser inteiro: {raw_state_port}") from exc
    state_require_gui = str(
        e.get("JARVIS_REQUIRE_GUI", "0")
    ).strip().lower() in ("1", "true", "yes", "on")
```

E no construtor `Config(...)` (após `ptt=ptt,`):

```python
        state_port=state_port,
        state_require_gui=state_require_gui,
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd voice && . .venv/bin/activate && pytest tests/test_config.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add voice/config.py voice/tests/test_config.py
git commit -m "feat(jarvis): config JARVIS_STATE_PORT e JARVIS_REQUIRE_GUI"
```

---

### Task 4: Emissão de transições no `voice_loop`

**Files:**
- Modify: `voice/loop.py`
- Modify: `voice/tests/test_voice_loop.py`

**Interfaces:**
- Consumes: `StateHub` (usa só `set`).
- Produces: `voice_loop(..., hub=None)`, `see_once(..., hub=None)`, `do_once(..., hub=None)` — `hub` é qualquer objeto com `set(state, detail=None)` (duck-typed). `hub=None` → nenhuma emissão.

- [ ] **Step 1: Escrever os testes que falham**

Acrescente ao fim de `voice/tests/test_voice_loop.py`:

```python
class FakeHub:
    def __init__(self):
        self.states = []

    def set(self, state, detail=None):
        self.states.append(state)

    def take_command(self):
        return None

    def subscribers(self):
        return 1


def test_voice_loop_emits_happy_path_states(monkeypatch):
    hub = FakeHub()
    monkeypatch.setattr("loop.record", lambda **k: "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: "faca algo")
    monkeypatch.setattr("loop.speak", lambda text, **k: None)

    class Client:
        def ask(self, task, timeout_s=None):
            return "resposta"

    voice_loop(client=Client(), iterations=1, record_seconds=1, config=CFG, hub=hub)
    assert hub.states == [
        "idle", "listening", "transcribing", "thinking", "speaking", "idle",
    ]


def test_voice_loop_emits_error_on_agent_failure(monkeypatch):
    from agent_client import AgentError

    hub = FakeHub()
    monkeypatch.setattr("loop.record", lambda **k: "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: "faca algo")
    monkeypatch.setattr("loop.speak", lambda text, **k: None)

    class Client:
        def ask(self, task, timeout_s=None):
            raise AgentError("boom")

    voice_loop(client=Client(), iterations=1, record_seconds=1, config=CFG, hub=hub)
    assert hub.states == [
        "idle", "listening", "transcribing", "thinking", "error", "speaking", "idle",
    ]


def test_voice_loop_without_hub_still_runs(monkeypatch):
    monkeypatch.setattr("loop.record", lambda **k: "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: "x")
    monkeypatch.setattr("loop.speak", lambda text, **k: None)

    class Client:
        def ask(self, task, timeout_s=None):
            return "r"

    voice_loop(client=Client(), iterations=1, record_seconds=1, config=CFG)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd voice && . .venv/bin/activate && pytest tests/test_voice_loop.py -q`
Expected: FAIL com `TypeError: voice_loop() got an unexpected keyword argument 'hub'`

- [ ] **Step 3: Implementar a emissão**

Em `voice/loop.py`, ajuste a assinatura de `voice_loop`:

```python
def voice_loop(client=None, iterations: int = 0, record_seconds: float | None = None,
               config=None, err=None, max_consecutive_errors: int = 3,
               hub=None, orphan_timeout_s: float = 15.0) -> None:
```

Logo após `consecutive_errors = 0`, emita o estado inicial:

```python
    if hub is not None:
        hub.set("idle")
```

No bloco de captura/transcrição, emita `listening`/`transcribing`/`error`:

```python
        try:
            if hub is not None:
                hub.set("listening")
            if cfg.input_mode == "auto":
                wav = record_auto(config=cfg)
                if not wav:
                    err.write("[voz] nada detectado\n")
                    err.flush()
                    consecutive_errors = 0
                    if hub is not None:
                        hub.set("idle")
                    continue
            elif cfg.input_mode == "ptt":
                wav = record_ptt(config=cfg)
            else:
                wav = record(seconds=secs, config=cfg)
            t_rec = time.monotonic()
            if hub is not None:
                hub.set("transcribing")
            text = transcribe(wav, config=cfg)
        except VoiceError as exc:
            if hub is not None:
                hub.set("error")
            if _voice_error(exc):
                return
            if hub is not None:
                hub.set("idle")
            continue
```

No caminho vazio (`nada transcrito`), emita `idle` antes do `continue`:

```python
        if not text:
            err.write("[voz] nada transcrito\n")
            err.flush()
            consecutive_errors = 0
            if hub is not None:
                hub.set("idle")
            continue
```

No caminho de visão, passe o hub:

```python
            try:
                see_once(strip_trigger(text, cfg.vision_trigger), err=err, config=cfg, hub=hub)
```

No turno do agente, emita `thinking`/`speaking`/`error`:

```python
        error = None
        t_agent0 = time.monotonic()
        if hub is not None:
            hub.set("thinking")
        try:
            answer = client.ask(text)
        except AgentError as exc:
            error = str(exc)
            answer = f"erro: {exc}"
            if hub is not None:
                hub.set("error")
        t_agent1 = time.monotonic()
        spoken = speechify(answer)
        aborted = False
        tts_failed = False
        t_tts0 = time.monotonic()
        try:
            if not muted and hub is not None:
                hub.set("speaking")
            if not muted:
                speak(spoken, config=cfg)
        except VoiceError as exc:
            tts_failed = True
            aborted = _voice_error(exc)
            err.write(f"[fallback texto] {answer}\n")
            err.flush()
```

No fim do turno (após `consecutive_errors = 0`), emita `idle`:

```python
        consecutive_errors = 0
        if hub is not None:
            hub.set("idle")
```

> **Nota:** `muted` é introduzido na Task 6; nesta task use `muted = False` como variável local logo antes do try do TTS (a Task 6 liga o comando). Para manter esta task independente, escreva:
> ```python
>         muted = False
>         try:
>             if not muted and hub is not None:
>                 hub.set("speaking")
>             if not muted:
>                 speak(spoken, config=cfg)
> ```

Ajuste `see_once` e `do_once` para aceitar e emitir `hub`:

```python
def see_once(prompt: str, out=None, err=None, config=None, hub=None) -> None:
```

Em `see_once`, antes de `answer = see(...)`:

```python
    if hub is not None:
        hub.set("thinking")
```

e antes do `speak(spoken, config=cfg)` (dentro do `try`):

```python
    try:
        if hub is not None:
            hub.set("speaking")
        speak(spoken, config=cfg)
    except VoiceError as exc:
```

e ao final de `see_once`:

```python
    if hub is not None:
        hub.set("idle")
```

Em `do_once`, assinatura `def do_once(prompt: str, out=None, err=None, config=None, hub=None) -> None:` e, imediatamente antes de `cmd = [cfg.opencode_bin, ...]`:

```python
    if hub is not None:
        hub.set("acting")
```

e após `out.flush()` (antes do `log_turn`):

```python
    if hub is not None:
        hub.set("idle")
```

- [ ] **Step 4: Rodar a suíte inteira e ver passar**

Run: `cd voice && . .venv/bin/activate && pytest -q`
Expected: PASS (os testes antigos continuam passando porque `hub` é opcional)

- [ ] **Step 5: Commit**

```bash
git add voice/loop.py voice/tests/test_voice_loop.py
git commit -m "feat(jarvis): voice_loop emite transicoes de estado (hub opcional)"
```

---

### Task 5: Wire do hub no `main` (cria/para; degrada sem indicador)

**Files:**
- Modify: `voice/loop.py`
- Modify: `voice/tests/test_voice_loop.py`

**Interfaces:**
- Consumes: `StateHub` (via `loop_mod.StateHub`).
- Produces: `_start_hub(cfg, err) -> StateHub | None`; `main` passa `hub=` e chama `stop()` em `finally`.

- [ ] **Step 1: Escrever os testes que falham**

Em `voice/tests/test_voice_loop.py`, **ajuste** os testes existentes que monkeypatcham `voice_loop` para aceitarem kwargs extras, e acrescente os novos.

Substitua o corpo de `test_main_voice_parses_iterations_and_stops`:

```python
def test_main_voice_parses_iterations_and_stops(monkeypatch):
    seen = {}
    monkeypatch.setattr(loop_mod, "ensure_server", lambda cfg: True)
    monkeypatch.setattr(loop_mod, "make_client", lambda cfg: "client")
    monkeypatch.setattr(loop_mod, "StateHub", lambda *a, **k: None)
    monkeypatch.setattr(
        loop_mod, "voice_loop",
        lambda c, **k: seen.update(n=k.get("iterations"), hub=k.get("hub")),
    )
    assert main(["--voice", "--once", "1"]) == 0
    assert seen["n"] == 1
    assert seen["hub"] is None
```

Substitua o corpo de `test_main_rejects_once_zero`:

```python
def test_main_rejects_once_zero(monkeypatch):
    called = []
    monkeypatch.setattr(loop_mod, "ensure_server", lambda cfg: True)
    monkeypatch.setattr(loop_mod, "make_client", lambda cfg: "client")
    monkeypatch.setattr(loop_mod, "StateHub", lambda *a, **k: None)
    monkeypatch.setattr(loop_mod, "voice_loop", lambda c, **k: called.append(k))
    assert main(["--voice", "--once", "0"]) == 2
    assert called == []
```

Substitua o corpo de `test_main_voice_handles_keyboard_interrupt`:

```python
def test_main_voice_handles_keyboard_interrupt(monkeypatch):
    monkeypatch.setattr(loop_mod, "ensure_server", lambda cfg: True)
    monkeypatch.setattr(loop_mod, "make_client", lambda cfg: "client")
    monkeypatch.setattr(loop_mod, "StateHub", lambda *a, **k: None)

    def boom(c, **k):
        raise KeyboardInterrupt
    monkeypatch.setattr(loop_mod, "voice_loop", boom)
    assert main(["--voice"]) == 0
```

Acrescente os novos testes:

```python
class FakeHubServer:
    def __init__(self, *a, **k):
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


def test_start_hub_starts_and_returns():
    cfg = Config(opencode_bin="/x/o", timeout_s=10, state_port=0)
    hub = loop_mod._start_hub(cfg, io.StringIO())
    try:
        assert hub is not None
        assert hub.subscribers() == 0
    finally:
        hub.stop()


def test_main_starts_and_stops_hub(monkeypatch):
    made = {}
    monkeypatch.setattr(loop_mod, "ensure_server", lambda cfg: True)
    monkeypatch.setattr(loop_mod, "make_client", lambda cfg: "client")

    def make_hub(*a, **k):
        made["hub"] = FakeHubServer()
        return made["hub"]
    monkeypatch.setattr(loop_mod, "StateHub", make_hub)
    monkeypatch.setattr(loop_mod, "voice_loop", lambda c, **k: None)
    assert main(["--voice", "--once", "1"]) == 0
    assert made["hub"].started is True
    assert made["hub"].stopped is True


def test_main_degrades_without_indicator_when_hub_fails(monkeypatch):
    err = io.StringIO()
    def boom(*a, **k):
        raise OSError("porta ocupada")
    monkeypatch.setattr(loop_mod, "StateHub", boom)
    conn = loop_mod._start_hub(load_config({}), err)
    assert conn is None
    assert "[aviso]" in err.getvalue()
```

Adicione `from config import load_config` ao topo do arquivo de teste.

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd voice && . .venv/bin/activate && pytest tests/test_voice_loop.py -q`
Expected: FAIL com `AttributeError: module 'loop' has no attribute '_start_hub'`

- [ ] **Step 3: Implementar**

Em `voice/loop.py`, importe o hub:

```python
from state import StateHub
```

Acrescente o helper antes de `def main`:

```python
def _start_hub(cfg, err):
    try:
        hub = StateHub(cfg.state_port)
        hub.start()
        return hub
    except Exception as exc:
        err.write(f"[aviso] indicador indisponivel ({exc}); seguindo sem ele\n")
        err.flush()
        return None
```

No `main`, no bloco `--voice`:

```python
        if "--voice" in args:
            iterations = _parse_once(args)
            if "--once" in args and iterations < 1:
                sys.stderr.write("[erro] --once exige N >= 1\n")
                sys.stderr.flush()
                return 2
            cfg = load_config()
            hub = _start_hub(cfg, sys.stderr)
            try:
                voice_loop(resolve_client(cfg, sys.stderr), iterations=iterations,
                           config=cfg, hub=hub)
            finally:
                if hub is not None:
                    hub.stop()
            return 0
```

No bloco `--see`:

```python
        if "--see" in args:
            i = args.index("--see")
            question = args[i + 1] if i + 1 < len(args) else ""
            cfg = load_config()
            hub = _start_hub(cfg, sys.stderr)
            try:
                see_once(question, config=cfg, hub=hub)
            except VoiceError as exc:
                sys.stderr.write(f"[erro] {exc}\n")
                sys.stderr.flush()
                return 1
            finally:
                if hub is not None:
                    hub.stop()
            return 0
```

No bloco `--do`:

```python
        if "--do" in args:
            i = args.index("--do")
            if i + 1 >= len(args):
                sys.stderr.write("[erro] --do exige um prompt\n")
                sys.stderr.flush()
                return 2
            cfg = load_config()
            hub = _start_hub(cfg, sys.stderr)
            try:
                do_once(args[i + 1], config=cfg, hub=hub)
            finally:
                if hub is not None:
                    hub.stop()
            return 0
```

- [ ] **Step 4: Rodar a suíte inteira e ver passar**

Run: `cd voice && . .venv/bin/activate && pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add voice/loop.py voice/tests/test_voice_loop.py
git commit -m "feat(jarvis): main sobe/para o StateHub e degrada sem indicador"
```

---

### Task 6: Comandos (`mute`/`pause`/`quit`) e anti-órfão

**Files:**
- Modify: `voice/loop.py`
- Modify: `voice/tests/test_voice_loop.py`

**Interfaces:**
- Consumes: `hub.take_command()`, `hub.subscribers()`, `cfg.state_require_gui`.
- Produces: `gui_lost(require_gui: bool, subscribers: int, last_gui_ts: float, now: float, timeout: float) -> bool`; `voice_loop` honrando comandos e encerrando quando o overlay some.

- [ ] **Step 1: Escrever os testes que falham**

Acrescente ao fim de `voice/tests/test_voice_loop.py`:

```python
class CmdHub:
    def __init__(self, cmds=None, subs=1):
        self.states = []
        self._cmds = list(cmds or [])
        self._subs = subs

    def set(self, state, detail=None):
        self.states.append(state)

    def take_command(self):
        return self._cmds.pop(0) if self._cmds else None

    def subscribers(self):
        return self._subs


class ClientOK:
    def ask(self, task, timeout_s=None):
        return "resposta"


def _patch_voice(monkeypatch, calls):
    monkeypatch.setattr("loop.record", lambda **k: calls.append("record") or "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: calls.append("stt") or "oi")
    monkeypatch.setattr("loop.speak", lambda text, **k: calls.append("tts"))


def test_gui_lost_helper():
    assert loop_mod.gui_lost(False, 0, 0.0, 100.0, 15.0) is False
    assert loop_mod.gui_lost(True, 1, 0.0, 100.0, 15.0) is False
    assert loop_mod.gui_lost(True, 0, 0.0, 10.0, 15.0) is False
    assert loop_mod.gui_lost(True, 0, 0.0, 20.0, 15.0) is True


def test_pause_command_skips_capture(monkeypatch):
    calls = []
    _patch_voice(monkeypatch, calls)
    hub = CmdHub(cmds=["pause"])
    cfg = Config(opencode_bin="/x/o", timeout_s=10, record_seconds=1,
                 input_mode="fixed", ptt=False, state_require_gui=True)
    voice_loop(client=ClientOK(), iterations=1, record_seconds=1, config=cfg, hub=hub)
    assert "record" not in calls


def test_mute_command_skips_tts_but_logs(monkeypatch):
    calls = []
    records = []
    _patch_voice(monkeypatch, calls)
    monkeypatch.setattr("loop.log_turn", lambda rec, config=None: records.append(rec))
    hub = CmdHub(cmds=["mute"])
    voice_loop(client=ClientOK(), iterations=1, record_seconds=1, config=CFG, hub=hub)
    assert "tts" not in calls
    assert len(records) == 1


def test_quit_command_stops_before_capture(monkeypatch):
    calls = []
    _patch_voice(monkeypatch, calls)
    hub = CmdHub(cmds=["quit"])
    voice_loop(client=ClientOK(), iterations=0, record_seconds=1, config=CFG, hub=hub)
    assert "record" not in calls


def test_orphan_exits_when_gui_gone(monkeypatch):
    calls = []
    _patch_voice(monkeypatch, calls)
    hub = CmdHub(subs=0)
    err = io.StringIO()
    cfg = Config(opencode_bin="/x/o", timeout_s=10, record_seconds=1,
                 input_mode="fixed", ptt=False, state_require_gui=True)
    # 1º tick = last_gui_ts (folga); 2º tick já estoura o timeout, antes de capturar.
    ticks = iter([0.0, 100.0, 100.0, 100.0])
    monkeypatch.setattr("loop.time.monotonic", lambda: next(ticks, 100.0))
    voice_loop(client=ClientOK(), iterations=0, record_seconds=1, config=cfg,
               hub=hub, err=err, orphan_timeout_s=15.0)
    assert "record" not in calls
    assert "overlay ausente" in err.getvalue()


def test_orphan_does_not_exit_with_subscriber(monkeypatch):
    calls = []
    _patch_voice(monkeypatch, calls)
    hub = CmdHub(subs=1)
    cfg = Config(opencode_bin="/x/o", timeout_s=10, record_seconds=1,
                 input_mode="fixed", ptt=False, state_require_gui=True)
    voice_loop(client=ClientOK(), iterations=1, record_seconds=1, config=cfg,
               hub=hub, orphan_timeout_s=15.0)
    assert "record" in calls
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd voice && . .venv/bin/activate && pytest tests/test_voice_loop.py -q`
Expected: FAIL com `AttributeError: module 'loop' has no attribute 'gui_lost'`

- [ ] **Step 3: Implementar**

Em `voice/loop.py`, acrescente o helper puro antes de `voice_loop`:

```python
def gui_lost(require_gui: bool, subscribers: int, last_gui_ts: float,
             now: float, timeout: float) -> bool:
    if not require_gui:
        return False
    if subscribers > 0:
        return False
    return (now - last_gui_ts) > timeout
```

No início de `voice_loop`, após o `hub.set("idle")` inicial, inicialize o relógio de GUI:

```python
    last_gui_ts = time.monotonic()
    muted = False
    paused = False
```

No topo do `while` (logo após `n += 1`), trate comandos e o anti-órfão:

```python
        if hub is not None:
            cmd = hub.take_command()
            while cmd is not None:
                if cmd == "quit":
                    return
                if cmd == "mute":
                    muted = not muted
                elif cmd == "pause":
                    paused = not paused
                cmd = hub.take_command()
            now = time.monotonic()
            if hub.subscribers() > 0:
                last_gui_ts = now
            elif gui_lost(cfg.state_require_gui, 0, last_gui_ts, now, orphan_timeout_s):
                err.write("[voz] overlay ausente; encerrando\n")
                err.flush()
                return
            if paused:
                hub.set("idle")
                continue
```

Remova o `muted = False` local que a Task 4 deixou antes do `try` do TTS (agora `muted` vem do escopo do loop).

> **Nota de ordem:** o `while iterations == 0 or n < iterations` já incrementou `n`; um `continue` por `pause` consome uma iteração. Nos testes isso é intencional (`iterations=1` encerra após o comando).

- [ ] **Step 4: Rodar a suíte inteira e ver passar**

Run: `cd voice && . .venv/bin/activate && pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add voice/loop.py voice/tests/test_voice_loop.py
git commit -m "feat(jarvis): comandos mute/pause/quit e anti-orfao do overlay"
```

---

### Task 7: GUI Tauri — scaffold, orbe e SSE

**Files:**
- Create: `gui/` (via scaffold) — depois editar:
  - Modify: `gui/src/index.html`
  - Modify: `gui/src/styles.css`
  - Modify: `gui/src/main.js`
  - Modify: `gui/src-tauri/tauri.conf.json`
  - Modify: `gui/src-tauri/capabilities/default.json`

**Interfaces:**
- Consumes: `GET /events` (SSE) e `GET /state` (Tasks 1-2).
- Produces: app Tauri "gui" com janela transparente, sem decoração, always-on-top, no canto; orbe reagindo ao estado.

**Pré-requisito (checar antes):** no Windows, `node --version`, `npm --version`, `rustc --version`, `cargo --version` devem responder. Se `rustc`/`cargo` faltarem, instale o Rust (rustup) antes deste task. O Tauri v2 usa o WebView2 (já presente no Windows 10/11).

- [ ] **Step 1: Scaffold (não-interativo)**

No Windows (fora do WSL), na raiz do projeto:

```bash
npm create tauri-app@latest gui -- --template vanilla --manager npm --identifier com.guilherme.jarvis
```

Se o prompt for interativo, escolha: frontend **vanilla**, package manager **npm**, template **JavaScript**, identifier `com.guilherme.jarvis`. Depois:

```bash
cd gui && npm install
```

Expected: cria `gui/` com `src/` (frontend vanilla) e `src-tauri/` (Rust).

- [ ] **Step 2: Baixar a dependência do app e rodar o template**

Run (no Windows, em `gui/`): `npm run tauri dev`
Expected: abre uma janela padrão do template (vamos substituir o conteúdo a seguir). Feche a janela.

- [ ] **Step 3: Escrever o frontend**

`gui/src/index.html`:

```html
<!doctype html>
<html lang="pt-br">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link rel="stylesheet" href="styles.css" />
    <title>jarvis</title>
  </head>
  <body>
    <div class="handle" data-tauri-drag-region title="arrastar">⋮⋮</div>
    <div id="orb" class="orb" data-state="offline"></div>
    <div id="label" class="label">offline</div>
    <div id="menu" class="menu hidden">
      <button data-cmd="mute">Mudo</button>
      <button data-cmd="pause">Pausar</button>
      <button id="brain" data-cmd="brain">Reiniciar cérebro</button>
      <button data-cmd="quit">Sair</button>
    </div>
    <script type="module" src="/main.js"></script>
  </body>
</html>
```

`gui/src/styles.css`:

```css
html, body {
  margin: 0;
  background: transparent;
  overflow: hidden;
  user-select: none;
  -webkit-user-select: none;
}

.handle {
  position: fixed;
  top: 2px;
  right: 34px;
  color: #475569;
  font: 12px system-ui;
  cursor: grab;
  padding: 2px 6px;
}

.orb {
  position: fixed;
  right: 18px;
  bottom: 18px;
  width: 64px;
  height: 64px;
  border-radius: 50%;
  cursor: pointer;
  --c: #64748b;
  background: radial-gradient(circle at 34% 30%, color-mix(in srgb, var(--c) 75%, white), var(--c));
  box-shadow: 0 0 22px color-mix(in srgb, var(--c) 65%, transparent);
}

.orb::after {
  content: "";
  position: absolute;
  inset: -8px;
  border-radius: 50%;
  border: 2px solid color-mix(in srgb, var(--c) 40%, transparent);
}

.orb[data-state="idle"] { --c: #64748b; animation: breathe 4.5s ease-in-out infinite; }
.orb[data-state="listening"] { --c: #22d3ee; animation: pulse 1.4s ease-in-out infinite; }
.orb[data-state="listening"]::after { animation: ripple 1.6s ease-out infinite; }
.orb[data-state="transcribing"] { --c: #a855f7; animation: spin 1.2s linear infinite; }
.orb[data-state="thinking"] { --c: #34d399; animation: pulse 1.1s ease-in-out infinite; }
.orb[data-state="speaking"] { --c: #f59e0b; animation: speak 0.55s ease-in-out infinite; }
.orb[data-state="acting"] { --c: #f43f5e; animation: spin 2.2s linear infinite; }
.orb[data-state="error"] { --c: #ef4444; animation: flash 0.7s steps(2) infinite; }
.orb[data-state="offline"] { --c: #475569; }

@keyframes breathe { 0%,100% { transform: scale(1); opacity: .72 } 50% { transform: scale(1.06); opacity: 1 } }
@keyframes pulse { 0%,100% { transform: scale(1) } 50% { transform: scale(1.14) } }
@keyframes ripple { 0% { transform: scale(.9); opacity: .8 } 100% { transform: scale(1.7); opacity: 0 } }
@keyframes spin { 0% { transform: rotate(0) scale(1.04) } 100% { transform: rotate(360deg) scale(1.04) } }
@keyframes speak { 0%,100% { transform: scaleY(1) } 50% { transform: scaleY(1.18) scaleX(.92) } }
@keyframes flash { 0%,100% { opacity: 1 } 50% { opacity: .25 } }

.label {
  position: fixed;
  right: 88px;
  bottom: 38px;
  display: none;
  color: #c7cedb;
  font: 12px system-ui;
  background: #0b0e14cc;
  border: 1px solid #2a2f3a;
  border-radius: 6px;
  padding: 3px 8px;
}

.label.show { display: block; }

.menu {
  position: fixed;
  right: 18px;
  bottom: 92px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  background: #0b0e14ee;
  border: 1px solid #2a2f3a;
  border-radius: 8px;
  padding: 6px;
}

.menu.hidden { display: none; }

.menu button {
  background: transparent;
  border: 0;
  color: #c7cedb;
  font: 12px system-ui;
  text-align: left;
  padding: 6px 10px;
  border-radius: 5px;
  cursor: pointer;
}

.menu button:hover { background: #1b1e27; }
```

`gui/src/main.js`:

```js
const PORT = 8765;
const base = `http://localhost:${PORT}`;

const LABELS = {
  idle: "aguardando",
  listening: "ouvindo",
  transcribing: "transcrevendo",
  thinking: "pensando",
  speaking: "falando",
  acting: "agindo",
  error: "erro",
  offline: "offline",
};

const orb = document.getElementById("orb");
const label = document.getElementById("label");
const menu = document.getElementById("menu");
const brain = document.getElementById("brain");

function apply(state) {
  orb.dataset.state = state;
  const text = LABELS[state] || state;
  label.textContent = text;
  brain.textContent = state === "offline" ? "Iniciar cérebro" : "Reiniciar cérebro";
}

apply("offline");

function connect() {
  const es = new EventSource(`${base}/events`);
  es.onmessage = (ev) => {
    try {
      apply(JSON.parse(ev.data).state);
    } catch (e) {
      /* ignora payload inválido */
    }
  };
  es.onerror = () => apply("offline");
}
connect();

orb.addEventListener("mouseenter", () => label.classList.add("show"));
orb.addEventListener("mouseleave", () => label.classList.remove("show"));
orb.addEventListener("click", () => menu.classList.toggle("hidden"));

async function command(cmd) {
  try {
    await fetch(`${base}/command`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cmd }),
    });
  } catch (e) {
    /* servidor fora do ar */
  }
  menu.classList.add("hidden");
}

menu.addEventListener("click", async (ev) => {
  const btn = ev.target.closest("button");
  if (!btn) return;
  const cmd = btn.dataset.cmd;
  if (cmd === "quit") {
    await command("quit");
    window.__TAURI__.window.getCurrentWindow().close();
  } else if (cmd === "brain") {
    await window.__TAURI__.core.invoke("start_brain");
  } else {
    await command(cmd);
  }
});
```

- [ ] **Step 4: Ajustar `tauri.conf.json`**

Em `gui/src-tauri/tauri.conf.json`, ajuste o objeto `app`:
- `app.withGlobalTauri`: `true` (necessário para `window.__TAURI__.core.invoke` no JS).
- `app.security.csp`: `"default-src 'self'; connect-src 'self' http://localhost:8765; style-src 'self' 'unsafe-inline'"`.
- Em `app.windows[0]`, garanta:

```json
{
  "label": "main",
  "title": "jarvis",
  "width": 120,
  "height": 120,
  "resizable": false,
  "decorations": false,
  "transparent": true,
  "alwaysOnTop": true,
  "skipTaskbar": true,
  "shadow": false
}
```

> Reconcile as chaves com o template gerado (nomes como `decorations`/`transparent`/`alwaysOnTop` pertencem ao bloco da janela); não remova chaves exigidas pelo template.

- [ ] **Step 5: Permissões de janela**

Em `gui/src-tauri/capabilities/default.json`, no array `permissions`, garanta:

```json
["core:default", "core:window:allow-start-dragging", "core:window:allow-close"]
```

- [ ] **Step 6: Verificação manual**

Run (Windows, em `gui/`): `npm run tauri dev`
Expected: uma janela pequena, sem moldura, no canto inferior direito, com o orbe **cinza** e o rótulo "offline" ao passar o mouse; clicar no orbe abre o menu. (O vermelho/estados só aparecem com o cérebro no ar — Task 8/produção.) Feche a janela.

- [ ] **Step 7: Commit**

```bash
git add gui
git commit -m "feat(jarvis): GUI Tauri com orbe e cliente SSE"
```

---

### Task 8: GUI — "iniciar cérebro" (Rust) e verificação fim-a-fim

**Files:**
- Modify: `gui/src-tauri/src/lib.rs` (ou `main.rs`, conforme o template)
- Modify: `docs/backlog.md`

**Interfaces:**
- Consumes: `start_brain` invocado por `main.js`; SSE + `/command` (Tasks 1-6).
- Produces: comando Tauri `start_brain` que sobe o loop no WSL.

- [ ] **Step 1: Implementar o comando Rust**

Edite `gui/src-tauri/src/lib.rs` para conter (e registre no builder):

```rust
const LOOP_CMD: &str =
    "cd ~/github/jarvis/voice && . .venv/bin/activate && \
     JARVIS_REQUIRE_GUI=1 python loop.py --voice";

#[tauri::command]
fn start_brain() -> Result<(), String> {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        std::process::Command::new("wsl.exe")
            .args(["--", "bash", "-lc", LOOP_CMD])
            .creation_flags(0x08000000) // CREATE_NO_WINDOW: sem flash de console
            .spawn()
            .map(|_| ())
            .map_err(|e| e.to_string())
    }
    #[cfg(not(windows))]
    {
        Err("start_brain so funciona no Windows".to_string())
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![start_brain])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

> Se o template usar `main.rs` com `fn main`, mantenha o `fn main` chamando `app_lib::run()` (padrão do `create-tauri-app`) e coloque `start_brain`/`run` no `lib.rs`.

- [ ] **Step 2: Verificação fim-a-fim (manual)**

1. No WSL, `cd voice && . .venv/bin/activate && python loop.py --voice` (deixe rodando).
2. No Windows, `cd gui && npm run tauri dev`.
Expected: o orbe sai de "offline" para **cinza/aguardando** e acompanha o estado durante um turno falado (ciano ao ouvir, roxo ao transcrever, verde ao pensar, âmbar ao falar, volta a cinza).
3. Feche o loop (Ctrl-C) e clique em "Iniciar cérebro": Expected: o loop sobe no WSL e o orbe reconecta (sai de offline).
4. Com `JARVIS_REQUIRE_GUI=1`, feche a janela do overlay: Expected: o loop encerra no WSL em ~15s (log `[voz] overlay ausente; encerrando`).

- [ ] **Step 3: Atualizar o backlog**

Em `docs/backlog.md`, no item 6, marque o v1 como feito e aponte para a spec/plano:

```markdown
**Fases:** v1 = **overlay/orbe + SSE** → FEITO (spec `docs/superpowers/specs/2026-09-28-jarvis-state-indicator-design.md`, plano `docs/superpowers/plans/2026-09-28-jarvis-state-indicator.md`) → v2 = reativo ao áudio → v3 = avatar animado.
```

- [ ] **Step 4: Commit**

```bash
git add gui/src-tauri/src/lib.rs docs/backlog.md
git commit -m "feat(jarvis): start_brain no overlay + backlog atualizado"
```

---

## Self-Review

**Cobertura da spec:**
- Seção 4 (`voice/state.py`) → Tasks 1-2. ✔
- Seção 4 (`config.py`) → Task 3. ✔
- Seção 4/5 (`loop.py`, emissão) → Tasks 4-6. ✔
- Seção 4/5 (orbe, cores, animações) → Task 7. ✔
- Seção 6 (comandos) → Tasks 2 (endpoint) + 6 (loop) + 8 (GUI). ✔
- Seção 7 (híbrido 1+2, anti-órfão, Startup) → Task 6 (anti-órfão) + Task 8 (iniciar cérebro); o atalho de Startup fica para a issue #1, conforme a spec. ✔
- Seção 8 (tratamento de erro) → Task 5 (`_start_hub` degrada) + Task 6 (órfão/cliente morto no handler). ✔
- Seção 9 (testes) → cada task tem seu ciclo. ✔

**Consistência de tipos/nomes:** `StateHub(port, host)`, `set/snapshot/subscribers/take_command/push_command/start/stop`, `gui_lost(...)`, `_start_hub(cfg, err)`, `start_brain` — usados de forma idêntica entre tasks. `hub=None` preserva compatibilidade.

**Placeholders:** nenhum "TODO/TBD"; o único ponto dependente do template é o `tauri.conf.json`/`lib.rs`, com instrução explícita de reconciliação e o código completo fornecido.

## Execution Handoff

Plano salvo em `docs/superpowers/plans/2026-09-28-jarvis-state-indicator.md`. Duas opções de execução:

1. **Subagent-Driven (recomendada)** — despacho um subagente novo por task, com review entre tasks e iteração rápida.
2. **Inline** — executo as tasks nesta sessão, em lotes com checkpoints de review.

Qual prefere?
