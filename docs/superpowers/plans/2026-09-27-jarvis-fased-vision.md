# Jarvis Fase D — Visão de tela Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** "olhar a tela" — capturar o desktop do Windows e perguntar a um modelo de visão, acionável por `python loop.py --see "..."` e por palavra-chave na voz.

**Architecture:** `voice/vision.py` isola dois efeitos (capturar via `ffmpeg.exe` gdigrab; perguntar via `opencode run -m <vision> -f <png>`). `loop.py` integra (flag `--see` + gatilho na voz) e loga o turno.

**Tech Stack:** Python 3.10 (WSL), `pytest`, `ffmpeg.exe` (gdigrab), `opencode run` (modelo de visão `opencode-go/deepseek-v4-flash-vision-exp`).

## Global Constraints

- Contratos: `vision.capture(out_path=None, config=None) -> str`; `vision.see(prompt, png_path, config=None) -> str`.
- `-f` (attach) **depois** da mensagem: `opencode run --pure <prompt> -m <vision_model> -f <png>`.
- Erros → `AgentError`/`VoiceError` claros; nunca crash.
- Acionamento **explícito**; a **imagem não é logada** (só prompt/resposta no `convlog`).
- `VISION_MODEL` default `opencode-go/deepseek-v4-flash-vision-exp`; `VISION_TRIGGER` default `olha`; `VISION_PNG` default `C:\Users\bguil\tools\shot.png`.
- Todo passo termina em commit.

## File Structure

```
voice/
  vision.py            # capture() + see()
  config.py            # + vision_model, vision_trigger, vision_png
  loop.py              # + --see e gatilho de voz
  tests/test_vision.py
  tests/test_loop_vision.py
```

---

### Task 1: `vision.py` + config

**Files:** Create `voice/vision.py`; Modify `voice/config.py`; Test `voice/tests/test_vision.py`.

**Interfaces:** Produces `capture`, `see`; Config fields `vision_model`, `vision_trigger`, `vision_png`.

- [ ] **Step 1: Testes que falham**

Create `voice/tests/test_vision.py`:
```python
import subprocess
import pytest
from config import Config
import vision

CFG = Config(opencode_bin="/x/opencode", timeout_s=10,
             ffmpeg_exe="/ff/ffmpeg.exe",
             vision_model="opencode-go/deepseek-v4-flash-vision-exp",
             vision_png="C:\\Users\\x\\tools\\shot.png")

def test_capture_builds_gdigrab(monkeypatch):
    seen = {}
    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(subprocess, "run", fake_run)
    out = vision.capture(config=CFG)
    joined = " ".join(seen["cmd"])
    assert "/ff/ffmpeg.exe" in joined
    assert "-f gdigrab" in joined
    assert "-i desktop" in joined
    assert out == "/mnt/c/Users/x/tools/shot.png"   # WSL path returned

def test_capture_failure_raises(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError()))
    with pytest.raises(Exception):
        vision.capture(config=CFG)

def test_see_message_before_f(monkeypatch):
    seen = {}
    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "uma tela com x\n", "")
    monkeypatch.setattr(subprocess, "run", fake_run)
    out = vision.see("o que tem na tela?", "/mnt/c/Users/x/tools/shot.png", config=CFG)
    cmd = seen["cmd"]
    assert cmd[0] == "/x/opencode"
    assert "o que tem na tela?" in cmd
    assert "-m" in cmd and "opencode-go/deepseek-v4-flash-vision-exp" in cmd
    assert "-f" in cmd and "/mnt/c/Users/x/tools/shot.png" in cmd
    assert cmd.index("o que tem na tela?") < cmd.index("-f")   # msg antes de -f
    assert out == "uma tela com x"
```

- [ ] **Step 2: Rodar e ver falhar** — `cd voice && . .venv/bin/activate && pytest tests/test_vision.py -q` → FAIL.

- [ ] **Step 3: Implementar**

`voice/config.py`: adicionar campos/defaults `vision_model`, `vision_trigger`, `vision_png` (env `VISION_MODEL`/`VISION_TRIGGER`/`VISION_PNG`).

Create `voice/vision.py`:
```python
import os
import subprocess

from config import Config, load_config
from tts import VoiceError


def _wsl_to_windows(p: str) -> str:
    if p.startswith("/mnt/") and len(p) > 6 and p[5].isalpha():
        drive = p[5].upper()
        rest = p[6:].replace("/", "\\")
        return f"{drive}:{rest}"
    return p


def _windows_to_wsl(p: str) -> str:
    if len(p) > 2 and p[1] == ":" and p[2] in "\\/":
        drive = p[0].lower()
        rest = p[3:].replace("\\", "/")
        return f"/mnt/{drive}/{rest}"
    return p


def capture(out_path: str | None = None, config: Config | None = None) -> str:
    cfg = config or load_config()
    win_path = out_path or cfg.vision_png
    cmd = [cfg.ffmpeg_exe, "-y", "-f", "gdigrab", "-i", "desktop", "-frames:v", "1", "-update", "1", win_path]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        raise VoiceError(f"falha ao capturar a tela (FFMPEG_EXE): {exc}") from exc
    if proc.returncode != 0:
        raise VoiceError(f"ffmpeg gdigrab falhou ({proc.returncode}): {proc.stderr.strip()[-200:]}")
    return _windows_to_wsl(win_path)


def see(prompt: str, png_path: str, config: Config | None = None) -> str:
    cfg = config or load_config()
    prompt = (prompt or "").strip() or "Descreva o que esta na tela."
    cmd = [cfg.opencode_bin, "run", "--pure", prompt, "-m", cfg.vision_model, "-f", png_path]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=cfg.timeout_s)
    except (OSError, subprocess.SubprocessError) as exc:
        raise VoiceError(f"falha na consulta de visao: {exc}") from exc
    if proc.returncode != 0:
        raise VoiceError(f"visao falhou ({proc.returncode}): {proc.stderr.strip()[:200]}")
    from agent_client import strip_opencode_noise
    return strip_opencode_noise(proc.stdout).strip()
```

> Add `strip_opencode_noise(text) -> str` to `voice/agent_client.py` (extract the existing ANSI/`^> ` cleanup into a shared helper; `RunClient` uses it too) if not already present.

- [ ] **Step 4: Rodar e ver passar** — `pytest tests/test_vision.py -q` → passa.

- [ ] **Step 5: Commit** — `git add voice && git commit -m "feat(jarvis): modulo de visao de tela (captura + modelo de visao)"`

---

### Task 2: Integração no loop (`--see` + gatilho) + verificação

**Files:** Modify `voice/loop.py`; Test `voice/tests/test_loop_vision.py`.

- [ ] **Step 1: Testes que falham**

Create `voice/tests/test_loop_vision.py`:
```python
import io
import loop

def test_see_once_uses_capture_and_see(monkeypatch):
    calls = {}
    monkeypatch.setattr(loop, "capture", lambda **k: calls.setdefault("cap", "/mnt/c/x.png") or "/mnt/c/x.png")
    monkeypatch.setattr(loop, "see", lambda p, png, **k: calls.setdefault("see", (p, png)) or "uma tela")
    monkeypatch.setattr(loop, "speak", lambda t, **k: calls.setdefault("tts", t))
    out = io.StringIO()
    loop.see_once("o que tem?", out=out, config=None)
    assert calls["cap"] == "/mnt/c/x.png"
    assert calls["see"][0] == "o que tem?"
    assert "uma tela" in out.getvalue() or calls.get("tts")

def test_voice_trigger_detection():
    assert loop.is_vision_request("olha o que tem na tela", "olha") is True
    assert loop.is_vision_request("qual a capital da franca", "olha") is False
```

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementar**

`voice/loop.py`:
- import `from vision import capture, see`; `from sanitize import speechify`.
- `def is_vision_request(text, trigger) -> bool: return text.strip().lower().startswith(trigger.lower())`.
- `def strip_trigger(text, trigger) -> str:` remove o prefixo do gatilho.
- `def see_once(prompt, out=None, err=None, config=None) -> None:`
  - `png = capture(config=config)`; `answer = see(prompt, png, config=config)`; `spoken = speechify(answer)`; escreve `answer` em `out`; `speak(spoken, config=config)`; loga via `convlog.log_turn` (sem a imagem).
- `main()`: parsing simples — se `--see` presente, chama `see_once(<pergunta>)` e retorna 0.
- `voice_loop`: se `is_vision_request(text, cfg.vision_trigger)` → `see_once(strip_trigger(...))`; senão o caminho normal.

- [ ] **Step 4: Rodar e ver passar** — suíte completa (`pytest -q`).

- [ ] **Step 5: Integração real**
```bash
cd /home/guilherme/github/jarvis/voice && . .venv/bin/activate
timeout 150 python loop.py --see "Descreva em uma frase o que aparece nesta tela."
```
Expected: imprime e fala uma descrição da tela (latência ~20–40 s pelo startup do `run`).

- [ ] **Step 6: Commit** — `git add voice docs/notes && git commit -m "feat(jarvis): visao de tela integrada a voz (--see + gatilho)"`

---

## Self-Review

**1. Cobertura do spec:** §2 arquitetura → Tasks 1-2; §3 contratos → Tasks 1-2; §5 erros → `VoiceError`/`AgentError`; §6 testes → Tasks 1-2; §9 sucesso → Task 2 Step 5.
**2. Placeholders:** nenhum.
**3. Consistência:** `capture`/`see`/`see_once`/`is_vision_request` com as assinaturas usadas nos testes; `VISION_MODEL` default idêntico em config e spec.
