# Jarvis Fase 1 — Unificação de Inferência e Delegação Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o opencode usar um orquestrador na nuvem (OpenCode Go) que delega sub-tarefas baratas a um modelo local (Ollama/qwen3:8b na GPU), de forma nativa e versionada no repo `jarvis`.

**Architecture:** Providers nativos do opencode (sem proxy na rota quente). O agente primário `orchestrator` roda `opencode-go/deepseek-v4-flash` e delega ao subagente `local-executor` (model `ollama/qwen3:8b`) via Task tool, restrito por `permission.task`. Ollama roda no Windows sobre Vulkan; o WSL alcança via `OLLAMA_HOST`.

**Tech Stack:** opencode (config JSON), Ollama 0.34.4 (Windows/Vulkan), OpenCode Go.

## Global Constraints

- Model id do orquestrador: `opencode-go/deepseek-v4-flash` (verbatim).
- Model id do executor local: `ollama/qwen3:8b` (verbatim).
- **Proibido** usar `qwen2.5-coder:7b` como executor — tool-calling quebrado (testado).
- `OLLAMA_HOST` deve estar definido no WSL (esperado: `172.19.32.1:11434`).
- Ollama do Windows acessível: `curl -s http://172.19.32.1:11434/api/version` → `{"version":"0.34.4"}`.
- `qwen3:8b` instalado no Ollama do Windows.
- Config versionada no repo, em `opencode.json` (escopo de projeto). Não editar o config global nesta fase.
- Todo passo de código termina em commit.

## File Structure

- `opencode.json` (novo) — config de projeto do opencode: provider `ollama` (com `qwen3:8b`) e agentes `orchestrator` + `local-executor`.
- `docs/notes/fase1-verification.md` (novo) — registro de verificação e medição da Fase 1.
- `docs/superpowers/specs/2026-09-26-jarvis-fase1-inference-design.md` (existente) — spec aprovada.

---

### Task 1: Expor `qwen3:8b` como provider no opencode

**Files:**
- Create: `opencode.json` (raiz do repo)
- Test: nenhum arquivo de teste; verificação por comando

**Interfaces:**
- Produces: provider id `ollama` com modelo `ollama/qwen3:8b` resolvível pelo opencode.

- [ ] **Step 1: Verificar que o modelo ainda NÃO está exposto (deve falhar)**

Run:
```bash
cd /home/guilherme/github/jarvis
opencode models | grep -c 'ollama/qwen3:8b'
```
Expected: `0`

E confirmar que o modelo existe no Ollama:
```bash
curl -s http://172.19.32.1:11434/api/tags | python3 -c "import sys,json;print('qwen3:8b' in [m['name'] for m in json.load(sys.stdin)['models']])"
```
Expected: `True`

- [ ] **Step 2: Criar `opencode.json`**

Create `opencode.json`:
```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "ollama": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Ollama (Windows - local)",
      "options": {
        "baseURL": "http://{env:OLLAMA_HOST}/v1"
      },
      "models": {
        "qwen3:8b": {
          "name": "Qwen3 8B (local, GPU)"
        }
      }
    }
  }
}
```

- [ ] **Step 3: Verificar que o modelo está exposto (deve passar)**

Run:
```bash
opencode models | grep 'ollama/qwen3:8b'
```
Expected: `ollama/qwen3:8b`

- [ ] **Step 4: Smoke test — o modelo responde via opencode**

Run:
```bash
opencode run -m ollama/qwen3:8b "Responda apenas com a palavra: pong"
```
Expected: saída contendo `pong`.

- [ ] **Step 5: Commit**

```bash
git add opencode.json
git commit -m "feat(jarvis): exponho o modelo local qwen3:8b no provider ollama"
```

---

### Task 2: Criar o subagente `local-executor`

**Files:**
- Modify: `opencode.json`
- Test: verificação por comando

**Interfaces:**
- Consumes: `ollama/qwen3:8b` (Task 1).
- Produces: subagente `local-executor` invocável via `@local-executor` e pela Task tool.

- [ ] **Step 1: Verificar que o agente ainda NÃO existe (deve falhar)**

Run:
```bash
opencode agent list | grep -c 'local-executor'
```
Expected: `0`

- [ ] **Step 2: Adicionar o bloco `agent.local-executor`**

Substituir o conteúdo de `opencode.json` por:
```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "ollama": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Ollama (Windows - local)",
      "options": {
        "baseURL": "http://{env:OLLAMA_HOST}/v1"
      },
      "models": {
        "qwen3:8b": {
          "name": "Qwen3 8B (local, GPU)"
        }
      }
    }
  },
  "agent": {
    "local-executor": {
      "description": "Executa sub-tarefas baratas e bem delimitadas no modelo local (GPU): extracoes, formatacoes, resumos curtos, boilerplate e chamadas de ferramenta simples. Use quando a tarefa NAO exigir raciocinio profundo; para planejamento/arquitetura, use a nuvem.",
      "mode": "subagent",
      "model": "ollama/qwen3:8b",
      "temperature": 0.1
    }
  }
}
```

- [ ] **Step 3: Verificar que o agente existe (deve passar)**

Run:
```bash
opencode agent list | grep 'local-executor'
```
Expected: linha contendo `local-executor`.

- [ ] **Step 4: Commit**

```bash
git add opencode.json
git commit -m "feat(jarvis): cria o subagente local-executor no modelo local"
```

---

### Task 3: Criar o agente primário `orchestrator` e restringir a delegação

**Files:**
- Modify: `opencode.json`
- Test: verificação por comando

**Interfaces:**
- Consumes: `local-executor` (Task 2).
- Produces: agente primário `orchestrator` (model `opencode-go/deepseek-v4-flash`) com `permission.task` permitindo apenas `local-executor`.

- [ ] **Step 1: Verificar que o agente ainda NÃO existe (deve falhar)**

Run:
```bash
opencode agent list | grep -c 'orchestrator'
```
Expected: `0`

- [ ] **Step 2: Adicionar o agente `orchestrator`**

Substituir o conteúdo de `opencode.json` por:
```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "ollama": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Ollama (Windows - local)",
      "options": {
        "baseURL": "http://{env:OLLAMA_HOST}/v1"
      },
      "models": {
        "qwen3:8b": {
          "name": "Qwen3 8B (local, GPU)"
        }
      }
    }
  },
  "agent": {
    "local-executor": {
      "description": "Executa sub-tarefas baratas e bem delimitadas no modelo local (GPU): extracoes, formatacoes, resumos curtos, boilerplate e chamadas de ferramenta simples. Use quando a tarefa NAO exigir raciocinio profundo; para planejamento/arquitetura, use a nuvem.",
      "mode": "subagent",
      "model": "ollama/qwen3:8b",
      "temperature": 0.1
    },
    "orchestrator": {
      "description": "Orquestrador: planeja, decompoe e delega sub-tarefas baratas ao local-executor, mantendo o raciocinio pesado na nuvem.",
      "mode": "primary",
      "model": "opencode-go/deepseek-v4-flash",
      "permission": {
        "task": {
          "*": "deny",
          "local-executor": "allow"
        }
      }
    }
  }
}
```

- [ ] **Step 3: Verificar que o agente existe (deve passar)**

Run:
```bash
opencode agent list | grep 'orchestrator'
```
Expected: linha contendo `orchestrator`.

- [ ] **Step 4: Verificar que o orquestrador usa o modelo da nuvem**

Run:
```bash
opencode run --agent orchestrator "Responda em uma frase curta quem e voce."
```
Expected: resposta em texto; e imediatamente depois:
```bash
"/mnt/c/Users/bguil/AppData/Local/Programs/Ollama/ollama.exe" ps
```
Expected: sem modelo local carregado (o orquestrador roda na nuvem).

- [ ] **Step 5: Commit**

```bash
git add opencode.json
git commit -m "feat(jarvis): cria o orchestrator (nuvem) e restringe a task ao local-executor"
```

---

### Task 4: Verificar a delegação e registrar a medição

**Files:**
- Create: `docs/notes/fase1-verification.md`
- Test: verificação por comando

**Interfaces:**
- Consumes: `orchestrator` (Task 3) e `local-executor` (Task 2).
- Produces: documento `docs/notes/fase1-verification.md` com os resultados.

- [ ] **Step 1: Delegação manual via @mention**

Run:
```bash
opencode run --agent orchestrator "@local-executor Responda apenas com a palavra: delegado-ok"
```
Expected: saída contendo `delegado-ok`.

- [ ] **Step 2: Confirmar que o modelo local foi carregado durante a delegação**

Run (imediatamente após o passo anterior):
```bash
"/mnt/c/Users/bguil/AppData/Local/Programs/Ollama/ollama.exe" ps
```
Expected: linha com `qwen3:8b` e `PROCESSOR` contendo `GPU`.

- [ ] **Step 3: Testar a delegação automática**

Run:
```bash
opencode run --agent orchestrator "Formate esta lista em Markdown com topicos: banana maca uva"
```
Expected: a tarefa simples é respondida (idealmente delegada ao `local-executor` sem mencao manual).

- [ ] **Step 4: Registrar resultados em `docs/notes/fase1-verification.md`**

Create `docs/notes/fase1-verification.md`:
```markdown
# Fase 1 — Verificação

Data: 2026-09-26

## Evidência de infraestrutura
- GPU: AMD Radeon RX 6750 XT (12 GB), Ollama Windows 0.34.4, `OLLAMA_VULKAN=true`.
- Inferência local: `codellama:7b-instruct` = 100% GPU, 85 tok/s.
- `qwen3:8b` = 100% GPU, `tool_calls` nativos OK.
- `qwen2.5-coder:7b` = tool-calling quebrado (rejeitado).

## Verificação da Fase 1
- [ ] `ollama/qwen3:8b` exposto no opencode
- [ ] subagente `local-executor` criado
- [ ] `orchestrator` (nuvem) criado com `permission.task` restrita
- [ ] delegação manual (`@local-executor`) funciona
- [ ] delegação automática funciona
- [ ] execução local confirmada em GPU (`ollama ps`)

## Medição (preencher)
- Latência média de uma sub-tarefa delegada: ____ s
- tok/s no `qwen3:8b`: ____
- Cota Go economizada: qualitativo (tokens da sub-tarefa que não foram para a nuvem)
- Qualidade: sub-tarefa correta? (sim/nao) — ____
```

- [ ] **Step 5: Commit**

```bash
git add docs/notes/fase1-verification.md
git commit -m "docs(jarvis): registro de verificacao da Fase 1"
```

---

### Task 5 (OPCIONAL): Failover passivo do primário via LiteLLM

> Só executar se a decisão for incluir LiteLLM já na Fase 1 (questão aberta do spec §9). Se não, pular esta task inteira.

**Files:**
- Create: `litellm/config.yaml`
- Create: `docs/notes/litellm-failover.md`
- Modify: `opencode.json` (apontar o `orchestrator` para o LiteLLM)

**Interfaces:**
- Produces: endpoint OpenAI-compatible local `http://127.0.0.1:4000/v1` com modelo `jarvis` (Go) e fallback `jarvis-local` (Ollama).

- [ ] **Step 1: Confirmar pré-requisitos**

Run:
```bash
python3 -m pip show litellm >/dev/null 2>&1 && echo "litellm ok" || echo "instalar: pip install 'litellm[proxy]'"
echo "OPENCODE_API_KEY definido? ${OPENCODE_API_KEY:+sim}"
```
Expected: decidir instalação; a chave do Go deve estar disponível em env (obtida de `~/.local/share/opencode/auth.json`).

- [ ] **Step 2: Criar `litellm/config.yaml`**

Create `litellm/config.yaml`:
```yaml
model_list:
  - model_name: jarvis
    litellm_params:
      model: openai/deepseek-v4-flash
      api_base: https://opencode.ai/zen/go/v1
      api_key: os.environ/OPENCODE_API_KEY
      extra_headers:
        user-agent: "jarvis/0.1"
        x-opencode-session: "jarvis-fase1"
  - model_name: jarvis-local
    litellm_params:
      model: ollama_chat/qwen3:8b
      api_base: http://172.19.32.1:11434

router_settings:
  fallbacks: [{"jarvis": ["jarvis-local"]}]
  num_retries: 2
  timeout: 60
```

- [ ] **Step 3: Subir o LiteLLM e testar**

Run:
```bash
litellm --config litellm/config.yaml --port 4000 &
sleep 5
curl -s http://127.0.0.1:4000/v1/models | python3 -c "import sys,json;print([m['id'] for m in json.load(sys.stdin)['data']])"
```
Expected: lista contendo `jarvis` e `jarvis-local`.

- [ ] **Step 4: Testar o failover (simular falha do Go)**

Run:
```bash
curl -s http://127.0.0.1:4000/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"jarvis","messages":[{"role":"user","content":"diga oi"}]}' | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('choices',[{}])[0].get('message',{}).get('content','ERRO'))"
```
Expected: resposta em texto. Repetir com `OPENCODE_API_KEY` inválido para confirmar que cai em `jarvis-local`.

- [ ] **Step 5: Apontar o `orchestrator` para o LiteLLM**

Em `opencode.json`, adicionar provider `litellm` (`baseURL: http://127.0.0.1:4000/v1`, model `jarvis`) e mudar `agent.orchestrator.model` para `litellm/jarvis`.

- [ ] **Step 6: Documentar em `docs/notes/litellm-failover.md` e commitar**

```bash
git add litellm/config.yaml docs/notes/litellm-failover.md opencode.json
git commit -m "feat(jarvis): failover passivo do primario via litellm"
```

---

## Self-Review

**1. Cobertura do spec:**
- §4.1 providers nativos → Tasks 1 e 3.
- §4.2 subagente `local-executor` → Task 2.
- §4.3 ajustes locais (`num_ctx`, modelo) → pré-condições globais; `num_ctx` é por request (não nesta fase de config).
- §4.4 LiteLLM opcional → Task 5 (opcional).
- §7 verificação → Task 4.
- §8 não-objetivos → fora do plano, corretamente.

**2. Placeholders:** sem `TBD`/`TODO`. Os `____` em `fase1-verification.md` são campos de medição preenchidos na execução (intencional).

**3. Consistência de tipos/nomes:** `ollama/qwen3:8b`, `opencode-go/deepseek-v4-flash`, `local-executor`, `orchestrator` usados de forma idêntica em todas as tasks.
