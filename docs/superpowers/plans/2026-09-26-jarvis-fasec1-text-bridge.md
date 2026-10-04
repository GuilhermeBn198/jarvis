# Jarvis Fase C1 — Ponte de texto (voice) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Um pacote `voice/` (WSL, Python) que recebe uma tarefa por stdin, chama o agente (`opencode run`) e imprime a resposta — o encanamento da Fase C **sem áudio**.

**Architecture:** Módulos puros com um único efeito cada (`subprocess`), testáveis com fakes. C1 usa `RunClient` (o `serve` de baixa latência entra em C2/C3).

**Tech Stack:** Python 3.10 (WSL), `pytest`.

## Global Constraints

- Python 3.10; venv em `voice/.venv`; testes com `pytest`.
- Contrato: `AgentClient.ask(task: str, timeout_s: int | None = None) -> str`.
- `OPENCODE_BIN` default `~/.opencode/bin/opencode`; `VOICE_TIMEOUT_S` default `300`.
- C1 **não** tem áudio; `--pure` no `opencode run` para evitar ruído de plugin.
- Erros viram `AgentError` claro (nunca crash).
- Todo passo termina em commit.

## File Structure

```
voice/
  config.py                 # env → Config(opencode_bin, timeout_s)
  agent_client.py           # RunClient.ask() via subprocess; AgentError
  loop.py                   # stdin → ask → stdout
  requirements-dev.txt      # pytest
  pytest.ini                # pythonpath = .
  README.md
  tests/test_config.py
  tests/test_agent_client.py
  tests/test_loop.py
```

---

### Task 1: Pacote `voice/` (config + client + loop + testes)

**Files:**
- Create: `voice/config.py`, `voice/agent_client.py`, `voice/loop.py`
- Create: `voice/requirements-dev.txt`, `voice/pytest.ini`, `voice/README.md`
- Test: `voice/tests/test_config.py`, `voice/tests/test_agent_client.py`, `voice/tests/test_loop.py`

**Interfaces:**
- Produces: `Config`, `load_config`, `AgentError`, `RunClient.ask`, `loop.main`.

- [ ] **Step 1: venv + pytest.ini**

```bash
cd ~/github/jarvis/voice 2>/dev/null || mkdir -p ~/github/jarvis/voice
cd ~/github/jarvis/voice
python3 -m venv .venv && . .venv/bin/activate && pip install -q pytest
```
Create `voice/requirements-dev.txt`:
```
pytest
```
Create `voice/pytest.ini`:
```
[pytest]
pythonpath = .
```

- [ ] **Step 2: Escrever os testes que falham**

Create `voice/tests/test_config.py`:
```python
from config import load_config, DEFAULT_TIMEOUT_S

def test_defaults():
    cfg = load_config({})
    assert cfg.opencode_bin.endswith("/.opencode/bin/opencode")
    assert cfg.timeout_s == DEFAULT_TIMEOUT_S

def test_env_overrides():
    cfg = load_config({"OPENCODE_BIN": "/x/opencode", "VOICE_TIMEOUT_S": "42"})
    assert cfg.opencode_bin == "/x/opencode"
    assert cfg.timeout_s == 42
```

Create `voice/tests/test_agent_client.py`:
```python
import subprocess
import pytest
from config import Config
from agent_client import RunClient, AgentError

CFG = Config(opencode_bin="/x/opencode", timeout_s=10)

def test_ask_returns_stdout(monkeypatch):
    seen = {}
    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="  resposta  \n", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    out = RunClient(CFG).ask("faca algo")
    assert out == "resposta"
    assert seen["cmd"][0] == "/x/opencode"
    assert seen["cmd"][1] == "run"
    assert seen["cmd"][-1] == "faca algo"

def test_empty_task_raises():
    with pytest.raises(AgentError):
        RunClient(CFG).ask("   ")

def test_missing_binary_raises(monkeypatch):
    def fake_run(*a, **k):
        raise FileNotFoundError()
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
```

Create `voice/tests/test_loop.py`:
```python
import io
from loop import run_stream
from agent_client import AgentError

class FakeClient:
    def __init__(self, replies): self._replies = replies
    def ask(self, task, timeout_s=None): return self._replies[task]

def test_run_stream_answers_each_line():
    out = io.StringIO()
    run_stream(io.StringIO("oi\nola\n"), out, FakeClient({"oi": "R1", "ola": "R2"}))
    assert out.getvalue().splitlines() == ["R1", "R2"]

def test_run_stream_skips_blank_and_reports_errors():
    class ErrClient:
        def ask(self, task, timeout_s=None): raise AgentError("falhou")
    out, err = io.StringIO(), io.StringIO()
    run_stream(io.StringIO("\nboa\n"), out, ErrClient(), err)
    assert out.getvalue() == ""
    assert "falhou" in err.getvalue()
```

- [ ] **Step 3: Rodar e ver falhar**

```bash
cd ~/github/jarvis/voice
. .venv/bin/activate && pytest -q
```
Expected: FAIL (`No module named 'config'`).

- [ ] **Step 4: Implementar `config.py`, `agent_client.py`, `loop.py`**

Create `voice/config.py`:
```python
import os
from dataclasses import dataclass

DEFAULT_OPENCODE_BIN = os.path.expanduser("~/.opencode/bin/opencode")
DEFAULT_TIMEOUT_S = 300


@dataclass(frozen=True)
class Config:
    opencode_bin: str
    timeout_s: int


def load_config(env: dict | None = None) -> Config:
    e = os.environ if env is None else env
    return Config(
        opencode_bin=e.get("OPENCODE_BIN", DEFAULT_OPENCODE_BIN),
        timeout_s=int(e.get("VOICE_TIMEOUT_S", DEFAULT_TIMEOUT_S)),
    )
```

Create `voice/agent_client.py`:
```python
import subprocess

from config import Config


class AgentError(RuntimeError):
    pass


class RunClient:
    def __init__(self, config: Config, cwd: str | None = None):
        self._cfg = config
        self._cwd = cwd

    def ask(self, task: str, timeout_s: int | None = None) -> str:
        task = (task or "").strip()
        if not task:
            raise AgentError("tarefa vazia")
        timeout = timeout_s or self._cfg.timeout_s
        try:
            proc = subprocess.run(
                [self._cfg.opencode_bin, "run", "--pure", task],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self._cwd,
            )
        except FileNotFoundError as exc:
            raise AgentError(f"opencode nao encontrado em {self._cfg.opencode_bin}") from exc
        except subprocess.TimeoutExpired as exc:
            raise AgentError(f"timeout ({timeout}s) ao chamar o agente") from exc
        if proc.returncode != 0:
            raise AgentError(f"opencode falhou ({proc.returncode}): {proc.stderr.strip()[:200]}")
        return proc.stdout.strip()
```

Create `voice/loop.py`:
```python
import sys

from agent_client import AgentError, RunClient
from config import load_config


def run_stream(inp, out, client, err=None) -> None:
    err = err if err is not None else sys.stderr
    for line in inp:
        task = line.strip()
        if not task:
            continue
        try:
            out.write(client.ask(task) + "\n")
        except AgentError as exc:
            err.write(f"[erro] {exc}\n")


def main() -> int:
    run_stream(sys.stdin, sys.stdout, RunClient(load_config()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Create `voice/README.md`:
```markdown
# voice (jarvis Fase C)

Ponte de texto: stdin → agente (opencode) → stdout.

## Rodar
    cd ~/github/jarvis/voice
    . .venv/bin/activate
    echo "responda apenas: ok" | python loop.py

## Testes
    . .venv/bin/activate && pytest -q
```

- [ ] **Step 5: Rodar e ver passar**

```bash
cd ~/github/jarvis/voice
. .venv/bin/activate && pytest -q
```
Expected: `11 passed` (config 2 + client 5 + loop 2 = 9; ajustar ao número real).

- [ ] **Step 6: Commit**

```bash
cd ~/github/jarvis
printf 'voice/.venv/\nvoice/**/__pycache__/\n' >> .gitignore
git add voice .gitignore
git commit -m "feat(jarvis): ponte de texto da voz (Fase C1)"
```

---

### Task 2: Verificação C1

**Files:**
- Create: `docs/notes/fasec1-verification.md`

- [ ] **Step 1: Suite completa**

```bash
cd ~/github/jarvis/voice
. .venv/bin/activate && pytest -q
```
Expected: todos passam (registrar o número real).

- [ ] **Step 2: Integração real (pode levar ~1–2 min pelo startup do opencode)**

```bash
cd ~/github/jarvis/voice
. .venv/bin/activate
timeout 200 bash -c 'echo "Responda apenas com a palavra: pong" | python loop.py'
```
Expected: saída contendo `pong`.

- [ ] **Step 3: Registrar**

Create `docs/notes/fasec1-verification.md`:
```markdown
# Fase C1 — Verificação (ponte de texto)

Data: 2026-09-26

## Unit
- [ ] `pytest -q` = ____ passed

## Integração (real)
- [ ] `echo "..." | python loop.py` retornou `pong`
- [ ] latência observada: ____ s

## Observações
(registrar o que aconteceu, inclusive lentidão do startup do opencode)
```

- [ ] **Step 4: Commit**

```bash
git add docs/notes/fasec1-verification.md
git commit -m "docs(jarvis): verificacao da Fase C1"
```

---

## Self-Review

**1. Cobertura do spec:** §2 arquitetura → Task 1; §3 contratos (`ask`) → Task 1; §4 estágio C1 → Tasks 1-2; §6 erros → Task 1; §7 testes → Tasks 1-2.
**2. Placeholders:** os `____`/`[ ]` em `fasec1-verification.md` são campos de registro.
**3. Consistência:** `Config`/`load_config`/`AgentError`/`RunClient.ask`/`run_stream` idênticos entre testes e implementação.
