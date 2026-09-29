# Jarvis — Streaming de TTS por sentença — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Falar a resposta do agente por sentença enquanto o texto ainda é gerado, reduzindo a latência percebida, com fallback para o caminho bloqueante atual.

**Architecture:** `ServeClient.stream()` envia via `POST /session/:id/prompt_async` e consome `GET /event` (SSE), filtrando a sessão e as partes de texto do assistant. Um `SentenceChunker` puro corta em pedaços faláveis; um `Speaker` (fila FIFO + 1 worker) sintetiza e toca em ordem. O loop usa esse caminho quando o backend é `serve`; qualquer falha cai no `ask()` bloqueante.

**Tech Stack:** Python 3.10 (WSL, stdlib), `pytest`; `opencode serve` (SSE `/event`); piper/ffplay (inalterados).

## Global Constraints

- Contrato do chunker (verbatim): `SentenceChunker(min_chars=15)` com `feed(delta: str) -> list[str]` e `flush() -> list[str]`.
- Contrato do speaker (verbatim): `Speaker(cfg)` com `say(text)`, `close()`, `join()`, atributos `error` e `first_speak_ts`.
- Contrato do stream (verbatim): `ServeClient.stream(task, on_delta, on_idle=None, timeout_s=None) -> str`.
- Contrato do turno (verbatim): `_stream_turn(client, text, cfg, hub, muted, t0, err) -> StreamResult`, com `StreamResult(answer, spoken, first_audio_s, streamed, failed)`.
- Env/config: `VOICE_STREAM_TTS` (default `true`), `VOICE_STREAM_IDLE_MS` (`400`), `VOICE_STREAM_MIN_CHARS` (`15`).
- Constante de omissão de código (verbatim): `"bloco de código omitido"`.
- **O streaming nunca derruba a voz**: qualquer falha cai no `ask()` bloqueante; o `Speaker` nunca propaga exceção para o loop.
- **`_stream_turn` NÃO chama `ask()`**: o fallback é responsabilidade do `voice_loop` (evita pedir a resposta duas vezes).
- **Não re-falar**: se já falou algo, o fallback não repete a resposta.
- `RunClient` não faz streaming; o caminho bloqueante atual permanece intacto (fakes sem `stream` seguem por ele).
- Testes: `cd voice && . .venv/bin/activate && pytest -q`.
- Todo passo termina em commit.

## File Structure

```
voice/
  stream.py             # novo: SentenceChunker + Speaker
  agent_client.py       # + ServeClient.stream / _consume_events / _post_no_content
  config.py             # + stream_tts, stream_idle_ms, stream_min_chars
  loop.py               # + StreamResult / _stream_turn / turno com streaming + fallback
  bench.py              # + first-audio (streaming vs bloqueante)
  tests/test_stream.py  # novo
  tests/test_agent_client.py   # + testes do stream
  tests/test_config.py  # + testes das novas envs
  tests/test_voice_loop.py     # + testes do turno com streaming
```

---

### Task 1: `SentenceChunker` (segmentação pura)

**Files:**
- Create: `voice/stream.py`
- Create: `voice/tests/test_stream.py`

**Interfaces:**
- Produces: `SentenceChunker(min_chars=15)`, `feed(delta) -> list[str]`, `flush() -> list[str]`; constante `CODE_OMIT = "bloco de código omitido"`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# voice/tests/test_stream.py
from stream import CODE_OMIT, SentenceChunker


def test_emits_complete_sentence():
    c = SentenceChunker(min_chars=5)
    assert c.feed("Olá, tudo bem? ") == ["Olá, tudo bem?"]


def test_does_not_split_decimal():
    c = SentenceChunker(min_chars=5)
    assert c.feed("O valor é 3.14 hoje. ") == ["O valor é 3.14 hoje."]


def test_does_not_split_abbreviation():
    c = SentenceChunker(min_chars=5)
    assert c.feed("Fale com o Sr. Silva agora. ") == ["Fale com o Sr. Silva agora."]


def test_short_sentence_merges_with_next():
    c = SentenceChunker(min_chars=20)
    assert c.feed("Oi. ") == []
    assert c.feed("Tudo bem com você? ") == ["Oi. Tudo bem com você?"]


def test_partial_without_terminator_waits_for_flush():
    c = SentenceChunker(min_chars=5)
    assert c.feed("sem ponto final") == []
    assert c.flush() == ["sem ponto final"]


def test_code_fence_is_held_and_replaced_by_placeholder():
    c = SentenceChunker(min_chars=1)
    out = c.feed("Veja:\n```\nprint(1)\n```\nFim. ")
    assert out == ["Veja:", CODE_OMIT, "Fim."]


def test_code_fence_split_across_deltas():
    c = SentenceChunker(min_chars=5)
    assert c.feed("```py") == []
    assert c.feed("codigo```") == [CODE_OMIT]


def test_flush_inside_open_fence_emits_placeholder_once():
    c = SentenceChunker(min_chars=5)
    assert c.feed("texto ```") == ["texto"]
    assert c.flush() == [CODE_OMIT]
    assert c.flush() == []


def test_flush_emits_pending_below_min():
    c = SentenceChunker(min_chars=50)
    assert c.feed("Oi. ") == []
    assert c.flush() == ["Oi."]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd voice && . .venv/bin/activate && pytest tests/test_stream.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'stream'`

- [ ] **Step 3: Implementar**

```python
# voice/stream.py
import queue
import threading
import time

from tts import VoiceError, speak

CODE_OMIT = "bloco de código omitido"
_CODE_FENCE = "```"
_TERMINATORS = ".!?…"
_ABBREV = ("sr", "sra", "dr", "dra", "etc", "ex", "obs", "p", "pag", "fig", "vs", "prof")


class SentenceChunker:
    """Acumula deltas e devolve pedaços faláveis (puro, sem I/O)."""

    def __init__(self, min_chars: int = 15):
        self._min = min_chars
        self._buf = ""
        self._pending = ""
        self._in_fence = False
        self._fence_notified = False

    def feed(self, delta: str) -> list[str]:
        self._buf += delta or ""
        out: list[str] = []
        self._drain(out)
        return out

    def flush(self) -> list[str]:
        out: list[str] = []
        if self._in_fence:
            self._buf = ""
            if not self._fence_notified:
                self._fence_notified = True
                out.append(CODE_OMIT)
        else:
            self._emit(self._buf.strip(), out)
            self._buf = ""
        if self._pending:
            out.append(self._pending)
            self._pending = ""
        return out

    def _emit(self, text: str, out: list[str]) -> None:
        if not text:
            return
        merged = (self._pending + " " + text).strip() if self._pending else text
        if len(merged) < self._min:
            self._pending = merged
            return
        self._pending = ""
        out.append(merged)

    def _drain(self, out: list[str]) -> None:
        while True:
            if self._in_fence:
                idx = self._buf.find(_CODE_FENCE)
                if idx == -1:
                    self._buf = self._buf[-2:]  # guarda possível fence parcial
                    return
                self._buf = self._buf[idx + 3:]
                self._in_fence = False
                if not self._fence_notified:
                    self._fence_notified = True
                    out.append(CODE_OMIT)
                continue
            fence_idx = self._buf.find(_CODE_FENCE)
            term_idx = self._find_terminator()
            if term_idx is not None and (fence_idx == -1 or term_idx < fence_idx):
                self._emit(self._buf[:term_idx + 1].strip(), out)
                self._buf = self._buf[term_idx + 1:].lstrip()
                continue
            if fence_idx != -1:
                self._emit(self._buf[:fence_idx].strip(), out)
                self._buf = self._buf[fence_idx + 3:]
                self._in_fence = True
                continue
            return

    def _find_terminator(self):
        b = self._buf
        for i, ch in enumerate(b):
            if ch not in _TERMINATORS:
                continue
            if i + 1 < len(b) and b[i + 1] not in " \n\t\"')]}":
                continue
            if ch == "." and self._protected(i):
                continue
            return i
        return None

    def _protected(self, i: int) -> bool:
        b = self._buf
        if i > 0 and b[i - 1].isdigit() and i + 1 < len(b) and b[i + 1].isdigit():
            return True
        j = i - 1
        while j >= 0 and b[j].isalpha():
            j -= 1
        return b[j + 1:i].lower() in _ABBREV
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd voice && . .venv/bin/activate && pytest tests/test_stream.py -q`
Expected: PASS (9 passed)

- [ ] **Step 5: Commit**

```bash
git add voice/stream.py voice/tests/test_stream.py
git commit -m "feat(jarvis): SentenceChunker para streaming de TTS"
```

---

### Task 2: `Speaker` (fila FIFO + worker + first_speak_ts)

**Files:**
- Modify: `voice/stream.py`
- Modify: `voice/tests/test_stream.py`

**Interfaces:**
- Consumes: `tts.speak` (monkeypatchável como `stream.speak`).
- Produces: `Speaker(cfg)` com `say(text)`, `close()`, `join()`, `error`, `first_speak_ts`.

- [ ] **Step 1: Escrever os testes que falham**

Acrescente a `voice/tests/test_stream.py`:

```python
import stream as stream_mod
from tts import VoiceError


class _Cfg:
    pass


def test_speaker_speaks_in_order(monkeypatch):
    spoken = []
    monkeypatch.setattr("stream.speak", lambda text, **k: spoken.append(text))
    sp = stream_mod.Speaker(_Cfg())
    sp.say("a")
    sp.say("b")
    sp.close()
    sp.join()
    assert spoken == ["a", "b"]
    assert sp.error is None
    assert sp.first_speak_ts is not None


def test_speaker_error_aborts_queue(monkeypatch):
    spoken = []

    def fake_speak(text, **k):
        spoken.append(text)
        if text == "b":
            raise VoiceError("boom")

    monkeypatch.setattr("stream.speak", fake_speak)
    sp = stream_mod.Speaker(_Cfg())
    sp.say("a")
    sp.say("b")
    sp.say("c")
    sp.close()
    sp.join()
    assert spoken == ["a", "b"]
    assert isinstance(sp.error, VoiceError)


def test_speaker_close_without_say_is_noop():
    sp = stream_mod.Speaker(_Cfg())
    sp.close()
    sp.join()
    assert sp.error is None
    assert sp.first_speak_ts is None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd voice && . .venv/bin/activate && pytest tests/test_stream.py -q`
Expected: FAIL com `AttributeError: module 'stream' has no attribute 'Speaker'`

- [ ] **Step 3: Implementar**

Acrescente ao fim de `voice/stream.py`:

```python
class Speaker:
    """Fila FIFO com 1 worker: fala os pedaços em ordem, sem derrubar o loop."""

    def __init__(self, cfg):
        self._cfg = cfg
        self._q: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self.error: VoiceError | None = None
        self.first_speak_ts: float | None = None

    def say(self, text: str) -> None:
        if not text:
            return
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        self._q.put(text)

    def _run(self) -> None:
        while True:
            item = self._q.get()
            if item is None:
                return
            try:
                if self.first_speak_ts is None:
                    self.first_speak_ts = time.monotonic()
                speak(item, config=self._cfg)
            except VoiceError as exc:
                self.error = exc
                while True:
                    try:
                        self._q.get_nowait()
                    except queue.Empty:
                        return

    def close(self) -> None:
        if self._thread is not None:
            self._q.put(None)

    def join(self) -> None:
        if self._thread is not None:
            self._thread.join()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd voice && . .venv/bin/activate && pytest tests/test_stream.py -q`
Expected: PASS (12 passed)

- [ ] **Step 5: Commit**

```bash
git add voice/stream.py voice/tests/test_stream.py
git commit -m "feat(jarvis): Speaker com fila FIFO, worker e first_speak_ts"
```

---

### Task 3: Config do streaming

**Files:**
- Modify: `voice/config.py`
- Modify: `voice/tests/test_config.py`

**Interfaces:**
- Produces: `Config.stream_tts: bool`, `Config.stream_idle_ms: int`, `Config.stream_min_chars: int`; constantes `DEFAULT_STREAM_TTS`, `DEFAULT_STREAM_IDLE_MS`, `DEFAULT_STREAM_MIN_CHARS`.

- [ ] **Step 1: Escrever os testes que falham**

Acrescente a `voice/tests/test_config.py`:

```python
def test_stream_defaults():
    from config import (DEFAULT_STREAM_IDLE_MS, DEFAULT_STREAM_MIN_CHARS,
                        DEFAULT_STREAM_TTS)
    cfg = load_config({})
    assert cfg.stream_tts is True
    assert cfg.stream_idle_ms == DEFAULT_STREAM_IDLE_MS == 400
    assert cfg.stream_min_chars == DEFAULT_STREAM_MIN_CHARS == 15
    assert DEFAULT_STREAM_TTS is True


def test_stream_env_overrides():
    cfg = load_config({
        "VOICE_STREAM_TTS": "0",
        "VOICE_STREAM_IDLE_MS": "250",
        "VOICE_STREAM_MIN_CHARS": "30",
    })
    assert cfg.stream_tts is False
    assert cfg.stream_idle_ms == 250
    assert cfg.stream_min_chars == 30


def test_stream_invalid_ints_raise():
    with pytest.raises(ValueError) as exc:
        load_config({"VOICE_STREAM_IDLE_MS": "abc"})
    assert "VOICE_STREAM_IDLE_MS" in str(exc.value)
    with pytest.raises(ValueError) as exc:
        load_config({"VOICE_STREAM_MIN_CHARS": "x"})
    assert "VOICE_STREAM_MIN_CHARS" in str(exc.value)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd voice && . .venv/bin/activate && pytest tests/test_config.py -q`
Expected: FAIL com `AttributeError: 'Config' object has no attribute 'stream_tts'`

- [ ] **Step 3: Implementar**

Em `voice/config.py`, junto das constantes:

```python
DEFAULT_STREAM_TTS = True
DEFAULT_STREAM_IDLE_MS = 400
DEFAULT_STREAM_MIN_CHARS = 15
```

Nos campos de `Config` (após `state_require_gui`):

```python
    stream_tts: bool = DEFAULT_STREAM_TTS
    stream_idle_ms: int = DEFAULT_STREAM_IDLE_MS
    stream_min_chars: int = DEFAULT_STREAM_MIN_CHARS
```

Em `load_config`, antes do `return Config(...)`:

```python
    stream_tts = str(e.get("VOICE_STREAM_TTS", "1")).strip().lower() in (
        "1", "true", "yes", "on",
    )
    raw_idle = e.get("VOICE_STREAM_IDLE_MS", DEFAULT_STREAM_IDLE_MS)
    try:
        stream_idle_ms = int(raw_idle)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"VOICE_STREAM_IDLE_MS deve ser inteiro: {raw_idle}") from exc
    raw_min = e.get("VOICE_STREAM_MIN_CHARS", DEFAULT_STREAM_MIN_CHARS)
    try:
        stream_min_chars = int(raw_min)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"VOICE_STREAM_MIN_CHARS deve ser inteiro: {raw_min}"
        ) from exc
```

E no construtor `Config(...)` (após `state_require_gui=...`):

```python
        stream_tts=stream_tts,
        stream_idle_ms=stream_idle_ms,
        stream_min_chars=stream_min_chars,
```

- [ ] **Step 4: Rodar e ver passar**

Run: `cd voice && . .venv/bin/activate && pytest tests/test_config.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add voice/config.py voice/tests/test_config.py
git commit -m "feat(jarvis): config do streaming de TTS"
```

---

### Task 4: `ServeClient.stream` (SSE `/event`)

**Files:**
- Modify: `voice/agent_client.py`
- Modify: `voice/tests/test_agent_client.py`

**Interfaces:**
- Produces: `ServeClient.stream(task, on_delta, on_idle=None, timeout_s=None) -> str`; helpers `_post_no_content(path, payload, timeout)`, `_consume_events(stream, session_id, on_delta, on_idle, timeout)`.

- [ ] **Step 1: VALIDAR o formato do `/event` (probe ao vivo)**

O formato exato dos eventos precisa ser confirmado antes de codar. Com um `opencode serve` no ar (porta 4096), rode:

```bash
cd voice && . .venv/bin/activate && python - <<'PY'
import json, threading, time, urllib.request

url = "http://127.0.0.1:4096"

def sse():
    with urllib.request.urlopen(url + "/event", timeout=30) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if line.startswith("data:"):
                try:
                    obj = json.loads(line[5:].strip())
                except ValueError:
                    continue
                print("EVENT:", obj.get("type"), json.dumps(obj.get("properties"))[:200])

t = threading.Thread(target=sse, daemon=True)
t.start()
time.sleep(0.5)
req = urllib.request.Request(url + "/session", data=b"{}",
    headers={"Content-Type": "application/json"}, method="POST")
sid = json.loads(urllib.request.urlopen(req, timeout=5).read())["id"]
req = urllib.request.Request(url + f"/session/{sid}/prompt_async",
    data=json.dumps({"parts": [{"type": "text", "text": "Diga apenas: ola"}],
                     "agent": "chat"}).encode(),
    headers={"Content-Type": "application/json"}, method="POST")
urllib.request.urlopen(req, timeout=5)
time.sleep(8)
PY
```

Expected: ver os `type` dos eventos. **Anote**: (a) o nome do evento de parte de texto (esperado `message.part.updated`); (b) se `properties.part.text` é **cumulativo** (texto todo até agora) ou delta; (c) o nome do evento de fim/ociosidade (esperado `session.idle`). Se forem diferentes, use os observados no Step 4 e nos testes.

- [ ] **Step 2: Escrever os testes que falham**

Acrescente a `voice/tests/test_agent_client.py`:

```python
import io
import json

from agent_client import AgentError, ServeClient
from config import Config


def _sse(*objs):
    return io.BytesIO(
        "".join("data: " + json.dumps(o) + "\n\n" for o in objs).encode()
    )


def _cfg():
    return Config(opencode_bin="/x/o", timeout_s=10, agent="chat")


def _part(pid, text, sid="S"):
    return {"type": "message.part.updated",
            "properties": {"part": {"id": pid, "type": "text",
                                    "sessionID": sid, "text": text}}}


def test_consume_events_cumulative_text_emits_deltas():
    client = ServeClient(_cfg())
    deltas = []
    stream = _sse(_part("p1", "Olá"), _part("p1", "Olá, tudo"),
                  {"type": "session.idle", "properties": {"sessionID": "S"}})
    text = client._consume_events(stream, "S", deltas.append, None, 10)
    assert deltas == ["Olá", ", tudo"]
    assert text == "Olá, tudo"


def test_consume_events_ignores_other_sessions():
    client = ServeClient(_cfg())
    deltas = []
    stream = _sse(_part("p1", "outro", sid="X"),
                  _part("p2", "meu", sid="S"),
                  {"type": "session.idle", "properties": {"sessionID": "S"}})
    client._consume_events(stream, "S", deltas.append, None, 10)
    assert deltas == ["meu"]


def test_consume_events_empty_raises():
    client = ServeClient(_cfg())
    stream = _sse({"type": "session.idle", "properties": {"sessionID": "S"}})
    try:
        client._consume_events(stream, "S", lambda d: None, None, 10)
        assert False, "deveria levantar"
    except AgentError:
        pass


def test_stream_posts_async_and_returns_text(monkeypatch):
    client = ServeClient(_cfg())
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
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `cd voice && . .venv/bin/activate && pytest tests/test_agent_client.py -q`
Expected: FAIL com `AttributeError: 'ServeClient' object has no attribute '_consume_events'`

- [ ] **Step 4: Implementar**

Em `voice/agent_client.py`, no topo, acrescente:

```python
import socket
import time
```

Acrescente estes métodos a `ServeClient` (após `ask`):

```python
    def _post_no_content(self, path: str, payload: dict, timeout: int) -> None:
        url = self._cfg.server_url.rstrip("/") + path
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (404, 410):
                raise _SessionGone(
                    f"sessao expirada no servidor (HTTP {exc.code})"
                ) from exc
            raise AgentError(
                f"falha ao falar com o servidor em {url} ({exc})"
            ) from exc
        except (OSError, ValueError) as exc:
            raise AgentError(f"falha ao falar com o servidor em {url} ({exc})") from exc

    def _consume_events(self, stream, session_id, on_delta, on_idle, timeout):
        deadline = time.monotonic() + timeout
        parts: dict[str, str] = {}
        done = False
        while not done:
            if time.monotonic() >= deadline:
                raise AgentError("timeout ao aguardar a resposta")
            try:
                raw = stream.readline()
            except (socket.timeout, TimeoutError):
                if on_idle is not None:
                    on_idle()
                continue
            if not raw:
                break
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if not payload:
                continue
            try:
                obj = json.loads(payload)
            except ValueError:
                continue
            etype = obj.get("type")
            props = obj.get("properties") or {}
            if etype == "message.part.updated":
                part = props.get("part") or {}
                if part.get("type") != "text":
                    continue
                if part.get("sessionID") and part["sessionID"] != session_id:
                    continue
                pid = part.get("id") or "?"
                new = part.get("text") or ""
                prev = parts.get(pid, "")
                delta = new[len(prev):] if new.startswith(prev) else new
                parts[pid] = new
                if delta:
                    on_delta(delta)
            elif etype in ("session.idle", "session.error"):
                sid = props.get("sessionID")
                if sid and sid != session_id:
                    continue
                done = True
        text = "".join(parts.values()).strip()
        if not text:
            raise AgentError("agente nao retornou resposta")
        return text

    def stream(self, task, on_delta, on_idle=None, timeout_s=None) -> str:
        task = (task or "").strip()
        if not task:
            raise AgentError("tarefa vazia")
        timeout = timeout_s if timeout_s is not None else self._cfg.timeout_s
        session_id = self._ensure_session(timeout)
        url = self._cfg.server_url.rstrip("/") + "/event"
        try:
            events = urllib.request.urlopen(url, timeout=timeout)
        except (OSError, ValueError) as exc:
            raise AgentError(f"falha ao assinar /event ({exc})") from exc
        try:
            payload = {"parts": [{"type": "text", "text": task}]}
            if self._cfg.agent:
                payload["agent"] = self._cfg.agent
            try:
                self._post_no_content(
                    f"/session/{session_id}/prompt_async", payload, timeout
                )
            except _SessionGone:
                self._session_id = None
                session_id = self._ensure_session(timeout)
                self._post_no_content(
                    f"/session/{session_id}/prompt_async", payload, timeout
                )
            return self._consume_events(
                events, session_id, on_delta, on_idle, timeout
            )
        finally:
            try:
                events.close()
            except OSError:
                pass
```

> **Nota:** os nomes de evento (`message.part.updated`, `session.idle`) foram os esperados no Step 1. Se o probe mostrar outros, use os observados aqui e nos testes.

- [ ] **Step 5: Rodar e ver passar**

Run: `cd voice && . .venv/bin/activate && pytest tests/test_agent_client.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add voice/agent_client.py voice/tests/test_agent_client.py
git commit -m "feat(jarvis): ServeClient.stream via prompt_async + SSE /event"
```

---

### Task 5: Turno com streaming no `voice_loop` (+ fallback)

**Files:**
- Modify: `voice/loop.py`
- Modify: `voice/tests/test_voice_loop.py`

**Interfaces:**
- Consumes: `SentenceChunker`, `Speaker` (`stream`), `cfg.stream_tts`, `cfg.stream_min_chars`.
- Produces: `StreamResult` (dataclass) e `_stream_turn(client, text, cfg, hub, muted, t0, err) -> StreamResult`.

**Contrato de `_stream_turn`:** tenta o streaming e fala por pedaço; **não** chama `ask()`. Retorna `StreamResult`:
- sucesso → `streamed=True`, `failed=None`, `answer` completo;
- falha sem ter falado nada → `streamed=False`, `spoken=[]`, `failed` preenchido (o loop fará o fallback bloqueante);
- falha após já ter falado → `streamed=False`, `spoken` não-vazio, `failed` preenchido (o loop **não** repete).

- [ ] **Step 1: Escrever os testes que falham**

Acrescente a `voice/tests/test_voice_loop.py` (o arquivo já importa `io`, `time`, `Config`, `loop as loop_mod`, `FakeHub`):

```python
from agent_client import AgentError


def _stream_cfg(**over):
    base = dict(opencode_bin="/x/o", timeout_s=10, agent_backend="serve",
                input_mode="fixed", ptt=False, stream_tts=True,
                stream_min_chars=5)
    base.update(over)
    return Config(**base)


def test_stream_turn_speaks_chunks_in_order(monkeypatch):
    spoken = []
    monkeypatch.setattr("stream.speak", lambda text, **k: spoken.append(text))

    class StreamClient:
        def stream(self, task, on_delta, on_idle=None, timeout_s=None):
            on_delta("Olá, tudo bem? ")
            on_delta("Como posso ajudar você hoje? ")
            return "Olá, tudo bem? Como posso ajudar você hoje?"

    hub = FakeHub()
    res = loop_mod._stream_turn(StreamClient(), "oi", _stream_cfg(), hub, False,
                                time.monotonic(), io.StringIO())
    assert res.streamed is True
    assert res.spoken == ["Olá, tudo bem?", "Como posso ajudar você hoje?"]
    assert spoken == res.spoken
    assert "speaking" in hub.states


def test_stream_turn_failure_before_speech(monkeypatch):
    class BoomClient:
        def stream(self, *a, **k):
            raise AgentError("sem sse")

    res = loop_mod._stream_turn(BoomClient(), "oi", _stream_cfg(), FakeHub(), False,
                                time.monotonic(), io.StringIO())
    assert res.streamed is False
    assert res.spoken == []
    assert res.failed == "sem sse"


def test_stream_turn_failure_after_speech_keeps_spoken(monkeypatch):
    monkeypatch.setattr("stream.speak", lambda text, **k: None)

    class HalfClient:
        def stream(self, task, on_delta, on_idle=None, timeout_s=None):
            on_delta("Uma frase completa. ")
            raise AgentError("caiu no meio")

    res = loop_mod._stream_turn(HalfClient(), "oi", _stream_cfg(), FakeHub(), False,
                                time.monotonic(), io.StringIO())
    assert res.streamed is False
    assert res.spoken == ["Uma frase completa."]
    assert res.failed == "caiu no meio"


def test_stream_turn_muted_does_not_speak(monkeypatch):
    spoken = []
    monkeypatch.setattr("stream.speak", lambda text, **k: spoken.append(text))

    class StreamClient:
        def stream(self, task, on_delta, on_idle=None, timeout_s=None):
            on_delta("Uma resposta qualquer. ")
            return "Uma resposta qualquer."

    res = loop_mod._stream_turn(StreamClient(), "oi", _stream_cfg(), FakeHub(), True,
                                time.monotonic(), io.StringIO())
    assert res.answer == "Uma resposta qualquer."
    assert spoken == []


def test_voice_loop_falls_back_to_ask_when_stream_fails(monkeypatch):
    calls = []
    monkeypatch.setattr("loop.record", lambda **k: "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: "oi")
    monkeypatch.setattr("loop.speak", lambda text, **k: calls.append(text))

    class BoomClient:
        def stream(self, *a, **k):
            raise AgentError("sem sse")

        def ask(self, task, timeout_s=None):
            return "resposta bloqueante"

    voice_loop(client=BoomClient(), iterations=1, record_seconds=1,
               config=_stream_cfg(), hub=FakeHub())
    assert calls == ["resposta bloqueante"]


def test_voice_loop_streams_without_calling_ask(monkeypatch):
    asked = []
    spoken = []
    monkeypatch.setattr("loop.record", lambda **k: "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: "oi")
    monkeypatch.setattr("stream.speak", lambda text, **k: spoken.append(text))

    class StreamClient:
        def stream(self, task, on_delta, on_idle=None, timeout_s=None):
            on_delta("Resposta em streaming. ")
            return "Resposta em streaming."

        def ask(self, *a, **k):
            asked.append(True)
            return "x"

    hub = FakeHub()
    voice_loop(client=StreamClient(), iterations=1, record_seconds=1,
               config=_stream_cfg(), hub=hub)
    assert asked == []
    assert spoken == ["Resposta em streaming."]
    assert "speaking" in hub.states
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `cd voice && . .venv/bin/activate && pytest tests/test_voice_loop.py -q`
Expected: FAIL com `AttributeError: module 'loop' has no attribute '_stream_turn'`

- [ ] **Step 3: Implementar `StreamResult` e `_stream_turn`**

Em `voice/loop.py`, importe:

```python
from dataclasses import dataclass

from stream import SentenceChunker, Speaker
```

Acrescente antes de `voice_loop`:

```python
@dataclass
class StreamResult:
    answer: str | None
    spoken: list[str]
    first_audio_s: float | None
    streamed: bool
    failed: str | None


def _first_audio(speaker, t0):
    if speaker is None or speaker.first_speak_ts is None:
        return None
    return round(speaker.first_speak_ts - t0, 3)


def _stream_turn(client, text, cfg, hub, muted, t0, err) -> StreamResult:
    """Tenta falar por streaming. NAO chama ask() — o fallback e do voice_loop."""
    chunker = SentenceChunker(min_chars=cfg.stream_min_chars)
    speaker = Speaker(cfg) if not muted else None
    spoken: list[str] = []
    failed: str | None = None
    answer: str | None = None

    def emit(chunks):
        for chunk in chunks:
            spoken_text = speechify(chunk)
            if spoken_text:
                spoken.append(spoken_text)
                if speaker is not None:
                    speaker.say(spoken_text)

    try:
        answer = client.stream(
            text,
            lambda d: emit(chunker.feed(d)),
            lambda: emit(chunker.flush()),
            timeout_s=cfg.timeout_s,
        )
        emit(chunker.flush())
    except (AgentError, VoiceError) as exc:
        failed = str(exc)
    finally:
        if speaker is not None:
            speaker.close()
            speaker.join()
            if speaker.error is not None and failed is None:
                failed = str(speaker.error)
    if failed is not None:
        err.write(f"[voz] streaming falhou ({failed})\n")
        err.flush()
    streamed = failed is None and answer is not None
    if streamed and hub is not None and spoken:
        _emit(hub, "speaking")
    return StreamResult(answer, spoken, _first_audio(speaker, t0), streamed, failed)
```

- [ ] **Step 4: Integrar no turno de `voice_loop`**

No `voice_loop`, **substitua todo o bloco** que hoje vai de `error = None` até a linha `spoken = speechify(answer)` (a que vem logo depois de `t_agent1 = time.monotonic()`) por:

```python
        error = None
        t_agent0 = time.monotonic()
        _emit(hub, "thinking")
        first_audio = None
        streamed = False
        tts_failed = False
        aborted = False
        answer = None
        if cfg.stream_tts and hasattr(client, "stream"):
            res = _stream_turn(client, text, cfg, hub, muted, t_agent0, err)
            first_audio = res.first_audio_s
            if res.streamed or res.spoken:
                answer = res.answer or " ".join(res.spoken)
                spoken = " ".join(res.spoken)
                streamed = res.streamed
                error = res.failed
        if answer is None:
            try:
                answer = client.ask(text)
            except AgentError as exc:
                error = str(exc)
                answer = f"erro: {exc}"
            spoken = speechify(answer)
            try:
                if not muted:
                    _emit(hub, "speaking")
                if not muted:
                    speak(spoken, config=cfg)
            except VoiceError as exc:
                tts_failed = True
                aborted = _voice_error(exc)
                err.write(f"[fallback texto] {answer}\n")
                err.flush()
        t_agent1 = time.monotonic()
```

> O restante do turno (o `log_turn(...)` e o tratamento `if tts_failed:` / `consecutive_errors = 0` / `_emit(hub, "idle")`) permanece como está. Garanta que a linha antiga `spoken = speechify(answer)` (pós-`t_agent1`) foi removida — agora `spoken` é definido no bloco acima.

- [ ] **Step 5: Log com `first_audio_s` e `stream`**

No `log_turn` do turno de voz, acrescente:

```python
                "stream": streamed,
                "first_audio_s": first_audio,
```

- [ ] **Step 6: Rodar a suíte inteira e ver passar**

Run: `cd voice && . .venv/bin/activate && pytest -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add voice/loop.py voice/tests/test_voice_loop.py
git commit -m "feat(jarvis): turno de voz com streaming de TTS + fallback"
```

---

### Task 6: Bench de first-audio + backlog

**Files:**
- Modify: `voice/bench.py`
- Modify: `docs/backlog.md`

- [ ] **Step 1: Medir first-audio (manual, com o serve no ar)**

```bash
cd voice && . .venv/bin/activate && python - <<'PY'
import time
from agent_client import ServeClient
from config import load_config
from stream import SentenceChunker

cfg = load_config()
client = ServeClient(cfg)
chunker = SentenceChunker(min_chars=cfg.stream_min_chars)
t0 = time.monotonic()
first = {"t": None}

def on_delta(d):
    for _ in chunker.feed(d):
        if first["t"] is None:
            first["t"] = time.monotonic() - t0

t = time.monotonic()
text = client.stream("Explique em 3 frases o que e fuso horario.", on_delta)
print("first_delta_chunk_s:", round(first["t"], 3) if first["t"] else None)
print("total_s:", round(time.monotonic() - t, 3))
print("texto:", text[:80])
PY
```

Expected: `first_delta_chunk_s` bem menor que `total_s` — é o ganho do streaming (o 1º pedaço fica pronto antes da resposta inteira).

- [ ] **Step 2: Registrar o número no backlog**

Em `docs/backlog.md`, item 1, marque o streaming e anote o número medido (substitua `<N>`/`<M>` pelos valores do Step 1):

```markdown
- [x] Streaming: começar a falar (TTS por sentença) enquanto o texto é gerado — FEITO (spec `docs/superpowers/specs/2026-09-29-jarvis-streaming-tts-design.md`, plano `docs/superpowers/plans/2026-09-29-jarvis-streaming-tts.md`). Medido: 1º pedaço em ~<N>s vs resposta completa ~<M>s.
```

- [ ] **Step 3: Commit**

```bash
git add voice/bench.py docs/backlog.md
git commit -m "docs(jarvis): streaming de TTS medido no backlog"
```

---

## Self-Review

**Cobertura da spec:**
- §4 `stream.py` (chunker + speaker + first_speak_ts) → Tasks 1-2. ✔
- §4 `agent_client.ServeClient.stream` → Task 4. ✔
- §4 `config` → Task 3. ✔
- §4/§5 loop + estados → Task 5. ✔
- §5 segmentação/sanitização → Task 1 + `speechify` na Task 5. ✔
- §6 log (`first_audio_s`, `stream`, `spoken`) → Task 5. ✔
- §7 erros (fallback, não re-falar, mute) → Task 5 (`_stream_turn` não chama `ask`; loop faz o fallback; `res.spoken` evita repetir). ✔
- §8 testes → cada task. ✔
- §4/§11 bench first-audio → Task 6. ✔

**Consistência de nomes:** `SentenceChunker(min_chars)`, `feed`/`flush`, `Speaker.say/close/join/error/first_speak_ts`, `ServeClient.stream/_consume_events/_post_no_content`, `StreamResult`/`_stream_turn` — idênticos entre tasks.

**Pontos corrigidos no self-review:** (1) `_stream_turn` **não** chama `ask()` (evita pedir a resposta duas vezes); (2) o teste do fence usa `min_chars=1` para "Fim." não ficar pendente; (3) `_stream_cfg` fixa `input_mode="fixed"` para o loop usar `record` (e não `record_auto`).

**Risco aberto e tratado:** o formato do `/event` é validado na Task 4 Step 1 (probe ao vivo) antes de codar; nomes default já vêm do esperado e os testes os pinam.

## Execution Handoff

Plano salvo em `docs/superpowers/plans/2026-09-29-jarvis-streaming-tts.md`. Duas opções:

1. **Subagent-Driven (recomendada)** — um subagente novo por task, com review entre elas.
2. **Inline** — executo as tasks nesta sessão em lotes com checkpoints.

Qual prefere?
