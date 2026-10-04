# Jarvis Fase C2+C3 — TTS e STT (voice) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Completar o loop de voz — falar a resposta (TTS via SAPI) e ouvir a tarefa (captura via `ffmpeg.exe` + STT via `faster-whisper`) — integrando com a ponte de texto da C1.

**Architecture:** A ponte segue **no WSL**; o áudio do Windows é alcançado por subprocess (`powershell.exe` para TTS, `ffmpeg.exe` para captura). Cada módulo tem **um** efeito e é testável com fakes.

**Tech Stack:** Python 3.10 (WSL), `pytest`, `faster-whisper` (CPU), `powershell.exe` (SAPI), `ffmpeg.exe` (dshow).

## Global Constraints

- Contratos (verbatim): `tts.speak(text: str, to_file: str | None = None) -> None`; `capture.record(seconds: float, out_path: str | None = None) -> str`; `stt.transcribe(wav_path: str) -> str`.
- Erros viram `VoiceError` claro (nunca crash); transcrição vazia → `""` (o loop não chama o agente).
- Sem segredos; sem mudanças em opencode/MCP/gate.
- Caminhos validados nesta máquina: `FFMPEG_EXE=/mnt/c/Users/<voce>/tools/ffmpeg/ffmpeg-master-latest-win64-gpl/bin/ffmpeg.exe`; `MIC_DEVICE=Microphone (FIFINE Microphone)`.
- `faster-whisper` instalado no venv (`voice/.venv`), modelo `base`, `device=cpu`, `compute_type=int8`.
- TTS via `powershell.exe -NoProfile -EncodedCommand <base64 UTF-16LE>` (evita quoting).
- Todo passo termina em commit.

## File Structure

```
voice/
  config.py        # + POWERSHELL_EXE, FFMPEG_EXE, MIC_DEVICE, WHISPER_MODEL, RECORD_SECONDS, LANGUAGE
  tts.py           # speak() via SAPI
  capture.py       # record() via ffmpeg.exe dshow
  stt.py           # transcribe() via faster-whisper
  loop.py          # + voice_loop(record_seconds) : grava→transcreve→pergunta→fala
  requirements.txt # faster-whisper
  tests/test_tts.py, tests/test_capture.py, tests/test_stt.py
```

---

### Task 1: TTS (`tts.speak`)

**Files:**
- Modify: `voice/config.py` (add `POWERSHELL_EXE`)
- Create: `voice/tts.py`
- Test: `voice/tests/test_tts.py`

**Interfaces:**
- Produces: `VoiceError`; `tts.speak(text, to_file=None) -> None`.

- [ ] **Step 1: Escrever os testes que falham**

Create `voice/tests/test_tts.py`:
```python
import subprocess
import pytest
from config import Config
from tts import speak, VoiceError

CFG = Config(opencode_bin="/x/opencode", timeout_s=10, powershell_exe="pwsh.exe")

def test_speak_runs_powershell_encodedcommand(monkeypatch):
    seen = {}
    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    speak("ola mundo", config=CFG)
    assert seen["cmd"][0] == "pwsh.exe"
    assert "-EncodedCommand" in seen["cmd"]

def test_empty_text_is_noop(monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: called.__setitem__("n", called["n"]+1))
    speak("   ", config=CFG)
    assert called["n"] == 0

def test_failure_raises(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(subprocess.SubprocessError("x")))
    with pytest.raises(VoiceError):
        speak("x", config=CFG)
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd ~/github/jarvis/voice
. .venv/bin/activate && pytest tests/test_tts.py -q
```
Expected: FAIL (`No module named 'tts'`).

- [ ] **Step 3: Implementar**

Em `voice/config.py`, adicionar ao `Config` o campo `powershell_exe: str = "powershell.exe"` e em `load_config` `powershell_exe=e.get("POWERSHELL_EXE", "powershell.exe")`.

Create `voice/tts.py`:
```python
import base64
import subprocess

from config import Config, load_config


class VoiceError(RuntimeError):
    pass


def _ps_script(text_b64: str, out: str | None) -> str:
    out_line = f"$s.SetOutputToWaveFile('{out}')" if out else "if ($false) {}"
    return (
        "Add-Type -AssemblyName System.Speech; "
        f"$t=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{text_b64}')); "
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"{out_line}; "
        "$s.Speak($t); $s.Dispose()"
    )


def _encoded(script: str) -> str:
    return base64.b64encode(script.encode("utf-16-le")).decode("ascii")


def speak(text: str, to_file: str | None = None, config: Config | None = None) -> None:
    text = (text or "").strip()
    if not text:
        return
    cfg = config or load_config()
    b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    script = _ps_script(b64, to_file)
    cmd = [cfg.powershell_exe, "-NoProfile", "-EncodedCommand", _encoded(script)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        raise VoiceError(f"falha ao falar via SAPI: {exc}") from exc
    if proc.returncode != 0:
        raise VoiceError(f"SAPI falhou ({proc.returncode}): {proc.stderr.strip()[:200]}")
```

- [ ] **Step 4: Rodar e ver passar**
```bash
cd ~/github/jarvis/voice && . .venv/bin/activate && pytest tests/test_tts.py -q
```
Expected: `3 passed`.

- [ ] **Step 5: Integração real (gera WAV, sem som)**
```bash
cd ~/github/jarvis/voice && . .venv/bin/activate
python -c "from tts import speak; speak('teste de audio', to_file='/tmp/opencode/tts.wav')"
ls -la /tmp/opencode/tts.wav
```
Expected: arquivo WAV criado (> 20 KB).

- [ ] **Step 6: Commit**
```bash
cd ~/github/jarvis
git add voice/config.py voice/tts.py voice/tests/test_tts.py
git commit -m "feat(jarvis): TTS via SAPI na voz (C2)"
```

---

### Task 2: STT + captura + loop de voz (C3)

**Files:**
- Modify: `voice/config.py` (add `ffmpeg_exe`, `mic_device`, `whisper_model`, `record_seconds`, `language`)
- Create: `voice/capture.py`, `voice/stt.py`
- Modify: `voice/loop.py` (add `voice_loop`)
- Create: `voice/requirements.txt`
- Test: `voice/tests/test_capture.py`, `voice/tests/test_stt.py`, `voice/tests/test_voice_loop.py`

**Interfaces:**
- Consumes: `tts.speak`, `agent_client.RunClient`, `config.load_config`.
- Produces: `capture.record(seconds, out_path=None) -> str`; `stt.transcribe(wav_path) -> str`; `loop.voice_loop(record_seconds=None, ...) -> None`.

- [ ] **Step 1: Testes que falham**

Create `voice/tests/test_capture.py`:
```python
import subprocess, pytest
from config import Config
from capture import record, VoiceError

CFG = Config(opencode_bin="/x/o", timeout_s=10, ffmpeg_exe="/ff/ffmpeg.exe", mic_device="Mic X", record_seconds=5)

def test_record_builds_dshow_command(monkeypatch, tmp_path):
    seen = {}
    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(subprocess, "run", fake_run)
    out = str(tmp_path / "a.wav")
    record(3, out_path=out, config=CFG)
    joined = " ".join(seen["cmd"])
    assert "/ff/ffmpeg.exe" in joined
    assert "-f dshow" in joined
    assert 'audio=Mic X' in joined
    assert "-t 3" in joined
    assert out in seen["cmd"]

def test_missing_ffmpeg_raises(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError()))
    with pytest.raises(VoiceError):
        record(1, out_path="/tmp/x.wav", config=CFG)
```

Create `voice/tests/test_stt.py`:
```python
import pytest
from config import Config
import stt as stt_mod

CFG = Config(opencode_bin="/x/o", timeout_s=10, whisper_model="base", language="pt")

def test_transcribe_joins_segments(monkeypatch):
    class Seg:
        def __init__(self, t): self.text = t
    class Model:
        def transcribe(self, path, language=None, beam_size=1):
            return [Seg(" ola"), Seg(" mundo")], type("I", (), {"language": "pt", "duration": 1.0})()
    monkeypatch.setattr(stt_mod, "_load_model", lambda cfg: Model())
    assert stt_mod.transcribe("/tmp/a.wav", config=CFG) == "ola mundo"

def test_empty_file_returns_empty(monkeypatch):
    class Model:
        def transcribe(self, path, language=None, beam_size=1):
            return [], type("I", (), {"language": "pt", "duration": 0.0})()
    monkeypatch.setattr(stt_mod, "_load_model", lambda cfg: Model())
    assert stt_mod.transcribe("/tmp/a.wav", config=CFG) == ""
```

Create `voice/tests/test_voice_loop.py`:
```python
from loop import voice_loop

def test_voice_loop_orchestrates(monkeypatch):
    calls = []
    monkeypatch.setattr("loop.record", lambda **k: calls.append("record") or "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: calls.append("stt") or "faca algo")
    monkeypatch.setattr("loop.speak", lambda text, **k: calls.append("tts"))

    class Client:
        def ask(self, task, timeout_s=None):
            calls.append("ask")
            return "resposta"
    voice_loop(client=Client(), iterations=1, record_seconds=1)
    assert calls == ["record", "stt", "ask", "tts"]

def test_voice_loop_empty_transcript_skips_agent(monkeypatch):
    calls = []
    monkeypatch.setattr("loop.record", lambda **k: calls.append("record") or "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: calls.append("stt") or "")
    monkeypatch.setattr("loop.speak", lambda text, **k: calls.append("tts"))
    class Client:
        def ask(self, *a, **k):
            calls.append("ask"); return "x"
    voice_loop(client=Client(), iterations=1, record_seconds=1)
    assert "ask" not in calls
```

- [ ] **Step 2: Rodar e ver falhar**
```bash
cd ~/github/jarvis/voice && . .venv/bin/activate && pytest tests/test_capture.py tests/test_stt.py tests/test_voice_loop.py -q
```
Expected: FAIL.

- [ ] **Step 3: Implementar `config.py` (novos campos), `capture.py`, `stt.py`, `loop.voice_loop`**

`voice/config.py`: adicionar campos com defaults validados:
`ffmpeg_exe` (env `FFMPEG_EXE`, default `/mnt/c/Users/<voce>/tools/ffmpeg/ffmpeg-master-latest-win64-gpl/bin/ffmpeg.exe`), `mic_device` (env `MIC_DEVICE`, default `Microphone (FIFINE Microphone)`), `whisper_model` (env `WHISPER_MODEL`, default `base`), `record_seconds` (env `RECORD_SECONDS`, default `5`), `language` (env `VOICE_LANGUAGE`, default `pt`), e `powershell_exe` (da Task 1).

`voice/capture.py`:
```python
import subprocess
from config import Config, load_config
from tts import VoiceError


def record(seconds: float, out_path: str | None = None, config: Config | None = None) -> str:
    cfg = config or load_config()
    out = out_path or "/tmp/jarvis_rec.wav"
    cmd = [cfg.ffmpeg_exe, "-f", "dshow", "-i", f"audio={cfg.mic_device}",
           "-t", str(seconds), "-y", out]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=int(seconds) + 30)
    except (OSError, subprocess.SubprocessError) as exc:
        raise VoiceError(f"falha ao gravar audio: {exc}") from exc
    if proc.returncode != 0:
        raise VoiceError(f"ffmpeg falhou ({proc.returncode}): {proc.stderr.strip()[-200:]}")
    return out
```

`voice/stt.py`:
```python
from config import Config, load_config
from tts import VoiceError

_MODEL = None


def _load_model(cfg: Config):
    from faster_whisper import WhisperModel
    return WhisperModel(cfg.whisper_model, device="cpu", compute_type="int8")


def _model(cfg: Config):
    global _MODEL
    if _MODEL is None:
        _MODEL = _load_model(cfg)
    return _MODEL


def transcribe(wav_path: str, config: Config | None = None) -> str:
    cfg = config or load_config()
    try:
        segments, _info = _model(cfg).transcribe(wav_path, language=cfg.language, beam_size=1)
    except Exception as exc:  # noqa: BLE001
        raise VoiceError(f"falha na transcricao: {exc}") from exc
    return " ".join(s.text.strip() for s in segments).strip()
```

`voice/loop.py`: adicionar, mantendo `run_stream`/`main`:
```python
from tts import speak
from capture import record
from stt import transcribe


def voice_loop(client, iterations: int = 0, record_seconds: float | None = None,
               config=None) -> None:
    from config import load_config
    cfg = config or load_config()
    secs = record_seconds if record_seconds is not None else cfg.record_seconds
    n = 0
    while iterations == 0 or n < iterations:
        n += 1
        wav = record(seconds=secs)
        text = transcribe(wav)
        if not text:
            continue
        try:
            answer = client.ask(text)
        except AgentError as exc:
            answer = f"erro: {exc}"
        speak(answer)
```

`voice/requirements.txt`:
```
faster-whisper
```

- [ ] **Step 4: Rodar e ver passar**
```bash
cd ~/github/jarvis/voice && . .venv/bin/activate && pytest -q
```
Expected: toda a suíte passa (registrar o número real).

- [ ] **Step 5: Integração real (curta)**
```bash
cd ~/github/jarvis/voice && . .venv/bin/activate
# grava 3s do mic real e transcreve (fale algo)
python -c "from capture import record; from stt import transcribe; w=record(3); print('WAV:', w); print('TEXTO:', transcribe(w))"
```
Expected: gera o WAV e imprime uma transcrição (ou vazio se houve silêncio).

- [ ] **Step 6: Commit**
```bash
cd ~/github/jarvis
git add voice
git commit -m "feat(jarvis): STT (faster-whisper) + captura (ffmpeg) + loop de voz (C3)"
```

---

## Self-Review

**1. Cobertura do spec:** §2 arquitetura → Tasks 1-2; §3 contratos (`speak`/`record`/`transcribe`) → Tasks 1-2; §4 C2/C3 → Tasks 1-2; §6 erros → `VoiceError`; §7 testes → unit + integração; §1.1 pivot → `stt.py` usa `faster-whisper`.
**2. Placeholders:** nenhum (contagens reais serão reportadas na execução).
**3. Consistência:** `VoiceError` compartilhado (definido em `tts.py`, importado por `capture`/`stt`); `record`/`transcribe`/`speak`/`voice_loop` com as assinaturas usadas nos testes.
