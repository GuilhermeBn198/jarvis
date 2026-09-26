# Jarvis — Fase 1: Unificação de Inferência e Delegação em Dois Níveis

- **Data:** 2026-09-26
- **Status:** proposta (aguardando revisão)
- **Escopo:** Fase 1 de um projeto maior ("jarvis" = camada de unificação de plataformas)

---

## 1. Contexto e objetivo

O **jarvis** é a camada que unifica duas plataformas de inferência:

- **Nuvem:** OpenCode Go (assinatura $10/mês, modelos open coding).
- **Local:** Ollama rodando no Windows sobre a GPU.

O objetivo final (fora do escopo desta fase) é um agente/harness acionado por **voz** que consegue **executar qualquer coisa no computador**. Esta fase constrói apenas a **fundação de inferência e delegação** sobre a qual voz, visão e ações serão adicionadas.

**Resultado esperado da Fase 1:** dentro do opencode, usar um **orquestrador na nuvem** (Go) que delega **sub-tarefas baratas** para um **modelo local** (GPU), funcionando de forma nativa e com falhas previsíveis.

---

## 2. Evidências validadas (ambiente real)

Levantadas e testadas durante o brainstorming:

| Item | Estado |
|---|---|
| opencode | Roda no **WSL2** (Ubuntu 22.04); host Windows em `172.19.32.1` (modo NAT) |
| Auth do opencode | `opencode-go` e `google` já autenticados |
| Provider Ollama no opencode | Já configurado (`Ollama (Windows - local)`, `baseURL=http://{env:OLLAMA_HOST}/v1`) |
| `OLLAMA_HOST` no WSL | Exportado dinamicamente no `.bashrc` (IP do gateway) |
| GPU | **AMD Radeon RX 6750 XT** (gfx1031 / Navi 22), 12 GB, driver 32.0.21045.5002 |
| Ollama Windows | 0.34.4, `OLLAMA_VULKAN=true`, `OLLAMA_HOST=0.0.0.0:11434` |
| Descoberta Vulkan | `library=Vulkan ... "AMD Radeon RX 6750 XT" total="12.0 GiB"` |
| **Inferência GPU** | ✅ `codellama:7b-instruct` → **100% GPU, 85 tok/s** |
| **`qwen3:8b`** | ✅ **100% GPU, `tool_calls` nativos corretos** (6,3 GB @ 8k ctx) |
| `qwen2.5-coder:7b` | ❌ tool-calling quebrado (devolve a chamada como texto, não em `tool_calls`) |
| ROCm | Não cobre a gfx1031; irrelevante — **Vulkan** é o caminho |

Fatos de plataforma relevantes:

- **OpenCode Go:** endpoint `https://opencode.ai/zen/go/v1`; id de modelo no config no formato `opencode-go/<model-id>`; exige **user-agent próprio** e header **`x-opencode-session`** para não ser marcado como abuso.
- **Jev (TypeSafe System One):** existe, mas é **Zen** (não Go), API proprietária (`/zen/v1/systemone`) — decidido como **fora da Fase 1**.
- **opencode suporta subagentes com modelo próprio** (`agent.<nome>.model`), invocáveis pelo agente primário via Task tool, com `permission.task` para restringir quem pode chamar quem.

---

## 3. Arquitetura alvo (conceitual)

Um **cascade em camadas**, com o caminho crítico local-first:

```
voz/texto
   │
   ▼
[ Classifier ]  ── intenção, é-comando?, risco, rota   (local, estruturado, sub-segundo)
   │
   ▼
[ Orchestrator ] ── plano/decomposição + resposta      (nuvem Go → fallback local)
   │
   ▼
[ Executor ]     ── tool-calls / ações                 (local)
   │
   ▼
[ SafetyGate ]   ── allow/ask/deny antes de irreversível (determinístico + classificador como sinal secundário)
```

### Interfaces (seams) — para trocar implementações sem retrabalho

- **`Classifier`** — entrada: texto/transcript + contexto → saída: `{intent, is_command, risk, route, confidence}`.
  - Implementação Fase 2: classificador local com structured output (JSON-schema do Ollama).
  - Implementação futura opcional: `JevClassifier` (nuvem, Zen) — plugável, não fundação.
- **`Orchestrator`** — entrada: tarefa classificada + contexto → plano/passos + resposta em linguagem natural.
  - Implementação Fase 1: LLM (Go primário, local como fallback).
- **`Executor`** — entrada: passo → tool-calls/ações.
  - Implementação Fase 1: ferramentas nativas do opencode.
- **`SafetyGate`** — entrada: ação proposta → `allow|ask|deny`.
  - Fase 1: sistema de `permission` do opencode (determinístico, baseline).
  - Futuro: allowlist/denylist + confirmação + classificador como **sinal secundário** (nunca gate único, nunca só nuvem).

**Princípio norteador:** o caminho crítico (classificador, executor, safety) é **local**; a nuvem serve para **qualidade de raciocínio** onde importa. Toda dependência de nuvem é opcional e trocável.

---

## 4. Design da Fase 1

### 4.1 Providers nativos (sem LiteLLM na rota quente)

- **Orquestrador:** `opencode-go/deepseek-v4-flash` (nativo, já autenticado).
- **Executor local:** `ollama/qwen3:8b` (nativo, via `OLLAMA_HOST`).

### 4.2 Delegação via subagente (mecanismo escolhido)

- Criar subagente **`local-executor`** com `model: ollama/qwen3:8b`.
  - `description` explícita orientando o orquestrador sobre **quando** delegar (tarefas baratas, repetitivas, formatação, extração, geração simples).
  - `permission.task` no agente primário restringindo a delegação permitida.
  - Visível (`hidden: false`) para permitir `@local-executor` manual.
- O orquestrador (Go) invoca o subagente pela Task tool; o custo da "decisão de delegar" é parte do raciocínio normal do orquestrador.

### 4.3 Ajustes locais

- Manter `num_ctx` explícito por request (evitar o `OLLAMA_CONTEXT_LENGTH=262144` atual, que estoura VRAM).
- Opcional: `OLLAMA_MAX_LOADED_MODELS=1` (evitar thrash de VRAM).
- Modelo local instalado: `qwen3:8b` (mantido). `qwen2.5-coder:7b` pode ser removido (falhou tool-calling).

### 4.4 LiteLLM (opcional, fora da rota quente)

- Papel reduzido a **failover passivo** do primário (Go estourou cota / indisponível → local).
- **Não é o roteador semântico** — o LiteLLM não decide por tipo de tarefa.
- Se implementado, roda no WSL e o opencode aponta o primário para ele. Caso contrário, a troca de modelo é manual.

---

## 5. Decisões travadas

1. **Delegação** = subagente nativo (não LiteLLM, não plugin) na Fase 1.
2. **Executor local** = `qwen3:8b` (tool-calling comprovado). **`qwen2.5-coder` rejeitado.**
3. **Orquestrador** = `deepseek-v4-flash` (Go).
4. **Topologia** = híbrida: opencode no WSL, Ollama no Windows. GPU via **Vulkan**.
5. **LiteLLM** = opcional, apenas failover passivo; fora da rota quente.
6. **Jev / MCP `local_llm`** = fora da Fase 1 (backlog, atrás das interfaces).
7. **Safety** = determinístico primeiro; classificador é sinal secundário.

---

## 6. Tratamento de erro

- **Tool-call inválido do local:** o subagente pode falhar; o orquestrador deve poder refazer/absorver. Medir taxa antes de confiar em delegação automática.
- **Cota Go esgotada:** sem LiteLLM → troca manual de modelo; com LiteLLM → fallback automático para local.
- **Ollama/GPU indisponível:** orquestrador continua na nuvem; delegação local falha de forma explícita (não silenciosa).
- **Cold start local (~9,5 s):** manter `keep_alive` aquecido quando a delegação é esperada.

---

## 7. Verificação

**Já executado (evidência):**
- Inferência GPU 100% Vulkan; `qwen3:8b` com `tool_calls` nativos.

**A executar na Fase 1:**
1. Configurar o subagente `local-executor` e confirmar que ele responde.
2. Confirmar delegação automática do orquestrador (Go) para o local numa tarefa barata.
3. Confirmar `@local-executor` manual.
4. Simular falha do Go (key inválida / cota) e documentar o comportamento (manual vs LiteLLM).
5. Comparar uma tarefa real: só-nuvem vs nuvem+delegação → medir tokens de cota economizados e impacto de latência/qualidade.

---

## 8. Não-objetivos (Fase 1)

- Voz (STT/TTS) — Fase 2.
- Captura de tela / visão — Fase 2.
- Automação de ações no Windows (GUI/mic) — Fase 3.
- Jev / System One.
- MCP `local_llm` com saída estruturada.

---

## 9. Riscos e questões abertas

| Risco | Mitigação |
|---|---|
| Delegar tool-calls a um 8B pode reduzir confiabilidade | Medir taxa de sucesso; medir antes de ampliar o escopo da delegação |
| Ganho é de **cota/privacidade**, não de velocidade (local ~80 tok/s vs nuvem) | Enquadrar a expectativa; usar para volume barato, não para latência |
| Granularidade grossa (sub-tarefa, não por tool-call) | Aceitável na Fase 1; Fase 2 = MCP `local_llm` |
| IP do host Windows muda no reboot | Já resolvido por `OLLAMA_HOST` dinâmico no `.bashrc`; alternativa futura = `networkingMode=mirrored` |
| Driver AMD "too old" para ROCm | Irrelevante (Vulkan usado); atualizar driver só se quisermos ROCm |

**Questão aberta:** implementar o failover passivo via LiteLLM já na Fase 1, ou manter troca manual e adiar o LiteLLM?

---

## 10. Backlog (Fases 2/3)

- **Fase 2:** classificador local estruturado (interface `Classifier`) + bridge de voz; livro `local_llm` (MCP) se a granularidade grossa incomodar.
- **Fase 3:** executor de ações no Windows + `SafetyGate` determinístico robusto.
- **Opcional:** `JevClassifier` (Zen) como implementação premium de `Classifier`; pré-router com `choice`/`noul`; gate de safety secundário.
