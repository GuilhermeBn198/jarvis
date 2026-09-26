# Jarvis Fase 2-A — MCP `delegate_local` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expor o modelo local (`qwen3:8b` na GPU via Ollama) como um tool MCP `delegate_local`, invocável pelo orquestrador na nuvem, com saída estruturada opcional.

**Architecture:** Servidor MCP local (Python + MCP Python SDK v2 (`MCPServer`), stdio) que traduz uma tool call em uma requisição HTTP `/api/chat` ao Ollama no Windows. `config.py` centraliza env/defaults; `ollama_client.py` encapsula o HTTP; `server.py` expõe o tool. Registrado no `opencode.json` como MCP `type: local`.

**Tech Stack:** Python 3.10 (WSL), `mcp` (SDK v2, `MCPServer`), `httpx`, `pytest`.

## Global Constraints

- Tool name: `delegate_local`; assinatura `delegate_local(prompt: str, json_schema: dict | None = None) -> str` (verbatim).
- Modelo local: `qwen3:8b`; `num_ctx` default `8192`; `think=false`; timeout default `180`s.
- `OLLAMA_HOST` é obrigatório (esperado `172.19.32.1:11434`); erro claro se ausente.
- O servidor **só faz inferência** — nenhuma execução de ação/arquivo/shell.
- Deps: `mcp`, `httpx` (runtime); `pytest` (dev).
- Todo passo de código termina em commit.

## File Structure

```
mcp_servers/delegate_local/
  config.py                 # env → Config (host, model, num_ctx, timeout)
  ollama_client.py          # HTTP POST /api/chat; erros tipados (OllamaError)
  server.py                 # MCP Python SDK v2 (`MCPServer`): define e registra o tool
  requirements.txt          # mcp, httpx
  requirements-dev.txt      # -r requirements.txt + pytest
  README.md                 # como rodar/testar
  tests/
    test_config.py
    test_ollama_client.py
    test_server.py
```

---

### Task 1: Scaffold + `config.py`

**Files:**
- Create: `mcp_servers/delegate_local/config.py`
- Create: `mcp_servers/delegate_local/requirements.txt`, `mcp_servers/delegate_local/requirements-dev.txt`
- Test: `mcp_servers/delegate_local/tests/test_config.py`

**Interfaces:**
- Produces: `Config` (dataclass com `ollama_host`, `model`, `num_ctx`, `timeout_s`, propriedade `chat_url`) e `load_config(env: dict | None = None) -> Config`.

- [ ] **Step 1: Criar os requirements**

Create `mcp_servers/delegate_local/requirements.txt`:
```
mcp
httpx
```
Create `mcp_servers/delegate_local/requirements-dev.txt`:
```
-r requirements.txt
pytest
```

- [ ] **Step 2: Criar venv e instalar (no diretório do servidor)**

Run:
```bash
cd /home/guilherme/github/jarvis/mcp_servers/delegate_local
python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements-dev.txt
python -c "import mcp, httpx, pytest; print('deps ok')"
```
Expected: `deps ok`

- [ ] **Step 3: Escrever os testes que falham**

Create `mcp_servers/delegate_local/tests/test_config.py`:
```python
import pytest
from config import load_config, DEFAULT_MODEL, DEFAULT_NUM_CTX, DEFAULT_TIMEOUT_S


def test_requires_ollama_host():
    with pytest.raises(ValueError):
        load_config({})


def test_defaults():
    cfg = load_config({"OLLAMA_HOST": "172.19.32.1:11434"})
    assert cfg.ollama_host == "172.19.32.1:11434"
    assert cfg.model == DEFAULT_MODEL
    assert cfg.num_ctx == DEFAULT_NUM_CTX
    assert cfg.timeout_s == DEFAULT_TIMEOUT_S


def test_strips_scheme_and_slash():
    cfg = load_config({"OLLAMA_HOST": "http://172.19.32.1:11434/"})
    assert cfg.ollama_host == "172.19.32.1:11434"
    assert cfg.chat_url == "http://172.19.32.1:11434/api/chat"


def test_env_overrides():
    cfg = load_config({
        "OLLAMA_HOST": "h:1",
        "DELEGATE_LOCAL_MODEL": "m",
        "DELEGATE_LOCAL_NUM_CTX": "4096",
        "DELEGATE_LOCAL_TIMEOUT_S": "30",
    })
    assert (cfg.model, cfg.num_ctx, cfg.timeout_s) == ("m", 4096, 30)
```

- [ ] **Step 4: Rodar e ver falhar**

Run:
```bash
cd /home/guilherme/github/jarvis/mcp_servers/delegate_local
. .venv/bin/activate && pytest tests/test_config.py -q
```
Expected: FAIL (`ModuleNotFoundError: No module named 'config'`).

- [ ] **Step 5: Implementar `config.py`**

Create `mcp_servers/delegate_local/config.py`:
```python
import os
from dataclasses import dataclass

DEFAULT_MODEL = "qwen3:8b"
DEFAULT_NUM_CTX = 8192
DEFAULT_TIMEOUT_S = 180


@dataclass(frozen=True)
class Config:
    ollama_host: str
    model: str
    num_ctx: int
    timeout_s: int

    @property
    def chat_url(self) -> str:
        return f"http://{self.ollama_host}/api/chat"


def load_config(env: dict | None = None) -> Config:
    e = os.environ if env is None else env
    host = (e.get("OLLAMA_HOST") or "").strip()
    if not host:
        raise ValueError("OLLAMA_HOST nao definido (ex.: 172.19.32.1:11434)")
    for scheme in ("http://", "https://"):
        if host.startswith(scheme):
            host = host[len(scheme):]
    host = host.rstrip("/")
    return Config(
        ollama_host=host,
        model=e.get("DELEGATE_LOCAL_MODEL", DEFAULT_MODEL),
        num_ctx=int(e.get("DELEGATE_LOCAL_NUM_CTX", DEFAULT_NUM_CTX)),
        timeout_s=int(e.get("DELEGATE_LOCAL_TIMEOUT_S", DEFAULT_TIMEOUT_S)),
    )
```

- [ ] **Step 6: Rodar e ver passar**

Run:
```bash
cd /home/guilherme/github/jarvis/mcp_servers/delegate_local
. .venv/bin/activate && pytest tests/test_config.py -q
```
Expected: `4 passed`

- [ ] **Step 7: Commit**

```bash
cd /home/guilherme/github/jarvis
printf 'mcp_servers/delegate_local/.venv/\nmcp_servers/delegate_local/**/__pycache__/\n.pytest_cache/\n' >> .gitignore
git add mcp_servers/delegate_local/config.py mcp_servers/delegate_local/requirements.txt mcp_servers/delegate_local/requirements-dev.txt mcp_servers/delegate_local/tests/test_config.py .gitignore
git commit -m "feat(jarvis): scaffold do MCP delegate_local + config"
```

---

### Task 2: `ollama_client.py`

**Files:**
- Create: `mcp_servers/delegate_local/ollama_client.py`
- Test: `mcp_servers/delegate_local/tests/test_ollama_client.py`

**Interfaces:**
- Consumes: `Config` (Task 1).
- Produces: `OllamaClient(config).chat(prompt: str, json_schema: dict | None = None) -> str`; exceção `OllamaError`.

- [ ] **Step 1: Escrever os testes que falham**

Create `mcp_servers/delegate_local/tests/test_ollama_client.py`:
```python
import httpx
import pytest
from config import Config
from ollama_client import OllamaClient, OllamaError

CFG = Config(ollama_host="h:1", model="qwen3:8b", num_ctx=8192, timeout_s=5)


class _Resp:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _client():
    return OllamaClient(CFG)


def test_success_free_text(monkeypatch):
    seen = {}

    def fake_post(url, json=None, timeout=None):
        seen["url"] = url
        seen["payload"] = json
        return _Resp(payload={"message": {"content": "ola"}})

    monkeypatch.setattr(httpx, "post", fake_post)
    out = _client().chat("diga ola")
    assert out == "ola"
    assert seen["url"] == "http://h:1/api/chat"
    assert seen["payload"]["model"] == "qwen3:8b"
    assert seen["payload"]["think"] is False
    assert seen["payload"]["options"] == {"num_ctx": 8192}
    assert "format" not in seen["payload"]


def test_schema_sets_format(monkeypatch):
    seen = {}

    def fake_post(url, json=None, timeout=None):
        seen["payload"] = json
        return _Resp(payload={"message": {"content": '{"n": 1}'}})

    monkeypatch.setattr(httpx, "post", fake_post)
    schema = {"type": "object", "properties": {"n": {"type": "number"}}}
    out = _client().chat("devolva n", schema)
    assert seen["payload"]["format"] == schema
    assert out == '{"n": 1}'


def test_schema_but_non_json_raises(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp(payload={"message": {"content": "nao json"}}))
    with pytest.raises(OllamaError):
        _client().chat("x", {"type": "object"})


def test_timeout_raises(monkeypatch):
    def fake_post(*a, **k):
        raise httpx.TimeoutException("t")

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(OllamaError):
        _client().chat("x")


def test_http_error_raises(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp(status_code=500, text="boom"))
    with pytest.raises(OllamaError):
        _client().chat("x")


def test_missing_content_raises(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp(payload={"message": {}}))
    with pytest.raises(OllamaError):
        _client().chat("x")
```

- [ ] **Step 2: Rodar e ver falhar**

Run:
```bash
cd /home/guilherme/github/jarvis/mcp_servers/delegate_local
. .venv/bin/activate && pytest tests/test_ollama_client.py -q
```
Expected: FAIL (`No module named 'ollama_client'`).

- [ ] **Step 3: Implementar `ollama_client.py`**

Create `mcp_servers/delegate_local/ollama_client.py`:
```python
import json
from typing import Any

import httpx

from config import Config


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, config: Config):
        self._cfg = config

    def chat(self, prompt: str, json_schema: dict | None = None) -> str:
        payload: dict[str, Any] = {
            "model": self._cfg.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": False,
            "options": {"num_ctx": self._cfg.num_ctx},
        }
        if json_schema is not None:
            payload["format"] = json_schema

        try:
            resp = httpx.post(self._cfg.chat_url, json=payload, timeout=self._cfg.timeout_s)
        except httpx.TimeoutException as exc:
            raise OllamaError(
                f"Timeout ({self._cfg.timeout_s}s) ao chamar Ollama em "
                f"{self._cfg.ollama_host} (cold start?)"
            ) from exc
        except httpx.HTTPError as exc:
            raise OllamaError(
                f"Ollama nao respondeu em {self._cfg.ollama_host}: {exc}"
            ) from exc

        if resp.status_code != 200:
            raise OllamaError(f"Ollama respondeu HTTP {resp.status_code}: {resp.text[:200]}")

        try:
            data = resp.json()
        except ValueError as exc:
            raise OllamaError("Resposta do Ollama nao e JSON") from exc

        content = (data.get("message") or {}).get("content")
        if content is None:
            raise OllamaError("Resposta do Ollama sem 'message.content'")

        if json_schema is not None:
            try:
                json.loads(content)
            except ValueError as exc:
                raise OllamaError(
                    "Modelo nao devolveu JSON valido apesar do json_schema"
                ) from exc

        return content
```

- [ ] **Step 4: Rodar e ver passar**

Run:
```bash
cd /home/guilherme/github/jarvis/mcp_servers/delegate_local
. .venv/bin/activate && pytest tests/test_ollama_client.py -q
```
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
cd /home/guilherme/github/jarvis
git add mcp_servers/delegate_local/ollama_client.py mcp_servers/delegate_local/tests/test_ollama_client.py
git commit -m "feat(jarvis): cliente HTTP do Ollama para o delegate_local"
```

---

### Task 3: `server.py` (MCPServer)

**Files:**
- Create: `mcp_servers/delegate_local/server.py`
- Test: `mcp_servers/delegate_local/tests/test_server.py`

**Interfaces:**
- Consumes: `load_config` (Task 1), `OllamaClient`/`OllamaError` (Task 2).
- Produces: tool MCP `delegate_local(prompt, json_schema=None) -> str`.

- [ ] **Step 1: Escrever os testes que falham**

Create `mcp_servers/delegate_local/tests/test_server.py`:
```python
import os
import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "172.19.32.1:11434")


def _import_server():
    import importlib
    import server
    return importlib.reload(server)


def test_empty_prompt_raises():
    server = _import_server()
    with pytest.raises(ValueError):
        server.delegate_local("   ")


def test_invalid_schema_raises():
    server = _import_server()
    with pytest.raises(ValueError):
        server.delegate_local("x", {"bad": object()})


def test_passes_through_to_client(monkeypatch):
    server = _import_server()
    seen = {}

    class FakeClient:
        def chat(self, prompt, json_schema=None):
            seen["prompt"] = prompt
            seen["schema"] = json_schema
            return "ok"

    monkeypatch.setattr(server, "_get_client", lambda: FakeClient())
    out = server.delegate_local("faca x", {"type": "object"})
    assert out == "ok"
    assert seen == {"prompt": "faca x", "schema": {"type": "object"}}
```

- [ ] **Step 2: Rodar e ver falhar**

Run:
```bash
cd /home/guilherme/github/jarvis/mcp_servers/delegate_local
. .venv/bin/activate && pytest tests/test_server.py -q
```
Expected: FAIL (`No module named 'server'`).

- [ ] **Step 3: Implementar `server.py`**

Create `mcp_servers/delegate_local/server.py`:
```python
import json

from mcp.server.mcpserver import MCPServer

from config import load_config
from ollama_client import OllamaClient, OllamaError

mcp = MCPServer("delegate_local")

_client: OllamaClient | None = None


def _get_client() -> OllamaClient:
    global _client
    if _client is None:
        _client = OllamaClient(load_config())
    return _client


@mcp.tool()
def delegate_local(prompt: str, json_schema: dict | None = None) -> str:
    """Executa uma sub-tarefa no modelo LOCAL (GPU) para economizar cota da nuvem.

    Use para trabalho VOLUMOSO, repetitivo ou mecanico: gerar saidas longas,
    boilerplate, ou extrair/estruturar texto em JSON. NAO use para raciocinio
    profundo, planejamento/arquitetura, nem tarefas triviais.

    Args:
        prompt: instrucao AUTO-CONTIDA (o modelo local nao ve o historico).
        json_schema: JSON Schema opcional; se enviado, a resposta sera JSON
            validado conforme o schema.
    """
    if not prompt or not prompt.strip():
        raise ValueError("prompt vazio")
    if json_schema is not None:
        try:
            json.dumps(json_schema)
        except (TypeError, ValueError) as exc:
            raise ValueError("json_schema nao e serializavel em JSON") from exc
    try:
        return _get_client().chat(prompt, json_schema)
    except OllamaError as exc:
        raise RuntimeError(str(exc)) from exc


if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 4: Rodar e ver passar**

Run:
```bash
cd /home/guilherme/github/jarvis/mcp_servers/delegate_local
. .venv/bin/activate && pytest -q
```
Expected: `17 passed` (config 4 + client 7 + server 6; inclui os testes de validação de json-schema).

- [ ] **Step 5: Escrever `README.md` do servidor**

Create `mcp_servers/delegate_local/README.md`:
```markdown
# delegate_local

Tool MCP que executa sub-tarefas no modelo local (Ollama GPU).

## Rodar
Requer `OLLAMA_HOST` definido. O opencode sobe o processo via stdio.

    OLLAMA_HOST=172.19.32.1:11434 .venv/bin/python server.py

## Testes
    python3 -m venv .venv && . .venv/bin/activate
    pip install -r requirements-dev.txt
    pytest -q
```

- [ ] **Step 6: Commit**

```bash
cd /home/guilherme/github/jarvis
git add mcp_servers/delegate_local/server.py mcp_servers/delegate_local/tests/test_server.py mcp_servers/delegate_local/README.md
git commit -m "feat(jarvis): servidor FastMCP do delegate_local"
```

---

### Task 4: Registrar o MCP no `opencode.json`

**Files:**
- Modify: `opencode.json`

**Interfaces:**
- Consumes: servidor (Task 3).
- Produces: MCP `delegate_local` disponível ao opencode.

- [ ] **Step 1: Verificar que o MCP ainda NÃO existe (deve falhar)**

Run:
```bash
cd /home/guilherme/github/jarvis
python3 -c "import json;print('delegate_local' in json.load(open('opencode.json')).get('mcp',{}))"
```
Expected: `False`

- [ ] **Step 2: Adicionar o bloco `mcp`**

No `opencode.json`, adicionar (preservando `provider` e `agent`):
```json
  "mcp": {
    "delegate_local": {
      "type": "local",
      "command": ["mcp_servers/delegate_local/.venv/bin/python", "mcp_servers/delegate_local/server.py"],
      "enabled": true,
      "environment": {
        "OLLAMA_HOST": "{env:OLLAMA_HOST}"
      }
    }
  }
```

Nota: o venv em `mcp_servers/delegate_local/.venv` precisa existir (é gitignored) ou o MCP falha ao subir. Crie-o com os passos da seção "Testes" do `mcp_servers/delegate_local/README.md`.

- [ ] **Step 3: Verificar descoberta**

Run:
```bash
cd /home/guilherme/github/jarvis
python3 -c "import json;d=json.load(open('opencode.json'));print('delegate_local' in d['mcp'], d['mcp']['delegate_local']['type'])"
opencode mcp --help 2>&1 | head -5
```
Expected: `True local` e uma ajuda de `opencode mcp` sem erro.

- [ ] **Step 4: Commit**

```bash
git add opencode.json
git commit -m "feat(jarvis): registra o MCP delegate_local no opencode"
```

---

### Task 5: Verificação e2e + medição

**Files:**
- Create: `docs/notes/fase2a-verification.md`

**Interfaces:**
- Consumes: tudo acima.

- [ ] **Step 1: Teste unit completo**

Run:
```bash
cd /home/guilherme/github/jarvis/mcp_servers/delegate_local
. .venv/bin/activate && pytest -q
```
Expected: `17 passed`

- [ ] **Step 2: Integração real (Ollama/GPU)**

Run:
```bash
cd /home/guilherme/github/jarvis/mcp_servers/delegate_local
. .venv/bin/activate
python - <<'PY'
from config import load_config
from ollama_client import OllamaClient
c = OllamaClient(load_config())
print("texto:", c.chat("Responda apenas com a palavra: pong")[:80])
print("json:", c.chat("Devolva um objeto com a chave n igual a 7", {"type":"object","properties":{"n":{"type":"number"}},"required":["n"]}))
PY
```
Expected: texto contendo `pong`; uma linha `json:` com JSON válido.
(depois: `"/mnt/c/Users/bguil/AppData/Local/Programs/Ollama/ollama.exe" ps` → `qwen3:8b`, GPU)

- [ ] **Step 3: E2E via opencode (o teste que importa)**

Run:
```bash
cd /home/guilherme/github/jarvis
timeout 600 opencode run --pure "Use a ferramenta delegate_local para gerar uma tabela Markdown com 15 linhas de comandos git e descricoes. Depois me diga se voce usou a ferramenta."
```
Expected: a resposta menciona o uso de `delegate_local`; registrar se o tool foi de fato invocado.

- [ ] **Step 4: Registrar resultados**

Create `docs/notes/fase2a-verification.md`:
```markdown
# Fase 2-A — Verificação (delegate_local)

Data: 2026-09-26

## Unit
- [ ] `pytest -q` = 17 passed

## Integração (real, GPU)
- [ ] texto livre retornou `pong`
- [ ] saída estruturada devolveu JSON válido
- [ ] `ollama ps` mostrou `qwen3:8b` em GPU

## E2E (opencode)
- [ ] MCP `delegate_local` descoberto (`opencode.json`)
- [ ] tool invocado numa tarefa adequada: (sim/nao) ____
- [ ] taxa de invocação observada (n de m) ____
- [ ] latência observada: ____ s

## Observações
(registrar o que aconteceu de fato, inclusive se o tool NAO foi invocado)
```

- [ ] **Step 5: Commit**

```bash
git add docs/notes/fase2a-verification.md
git commit -m "docs(jarvis): verificacao da Fase 2-A (delegate_local)"
```

---

## Self-Review

**1. Cobertura do spec:** arquitetura (§2 → Tasks 1-3), contrato do tool (§3 → Tasks 1-3), registro (§4 → Task 4), erros (§5 → Tasks 2-3), testes (§6 → Tasks 1-5), critério de sucesso (§9 → Task 5).
**2. Placeholders:** os `____` em `fase2a-verification.md` são campos de medição (intencional).
**3. Consistência:** `delegate_local`, `OllamaClient.chat`, `load_config`, `OllamaError` usados identicamente em todas as tasks; defaults (`qwen3:8b`, 8192, 180) idênticos em `config.py` e nos Global Constraints.
