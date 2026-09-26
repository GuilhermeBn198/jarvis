# Jarvis Fase 2-A — MCP `delegate_local` (Design)

- **Data:** 2026-09-26
- **Status:** aprovada (implementação)
- **Fase:** 2-A (de A→E). Depende da Fase 1 (concluída em `main`).
- **Objetivo:** expor o modelo local (`qwen3:8b` na GPU via Ollama) como **tool MCP** que o orquestrador na nuvem invoca **explicitamente**, com **saída estruturada opcional**.

---

## 1. Contexto e motivação

A Fase 1 unificou a inferência (nuvem OpenCode Go + local Ollama/Vulkan) mas a **delegação automática** para o modelo local **não funcionou** (0/4+): o orquestrador não escolhe *spawnar um subagente*. O aprendizado: **tool call é o modo nativo do modelo**; subagente não. A Fase 2-A substitui a delegação por subagente por um **tool** — algo que o modelo já usa naturalmente — reduzindo a fricção de invocação.

O modelo local roda no Windows (Ollama 0.34.4, `OLLAMA_VULKAN=true`, GPU AMD RX 6750 XT, ~52 tok/s), acessível do WSL via `OLLAMA_HOST=172.19.32.1:11434`.

## 2. Arquitetura

```
modelo nuvem (orquestrador)
   │  tool call: delegate_local(prompt, json_schema?)
   ▼
FastMCP server (Python, stdio)        ← processo local, subido pelo opencode
   │  HTTP POST /api/chat
   ▼
Ollama (Windows) → qwen3:8b (GPU)
```

### Estrutura de arquivos (nova)

```
mcp/delegate_local/
  server.py                  # FastMCP: define o tool, valida entrada, formata erros
  ollama_client.py           # cliente HTTP fino (POST /api/chat) — testável isolado
  config.py                  # leitura de OLLAMA_HOST, modelo, num_ctx, timeout (com defaults)
  requirements.txt           # mcp, httpx
  tests/
    test_ollama_client.py
    test_server.py
  README.md                  # como rodar e testar
```

**Fronteiras:**
- `ollama_client.py`: sabe *falar com o Ollama*; não sabe nada de MCP. Testável com um servidor HTTP fake.
- `server.py`: sabe *expor o tool*; delega toda a inferência ao client. Não conhece detalhes de transporte HTTP.
- `config.py`: fonte única dos parâmetros de ambiente (env → defaults).

## 3. Contrato do tool

```
delegate_local(prompt: str, json_schema: dict | None = None) -> str
```

- `prompt` (obrigatório): instrução autocontida (o modelo local não vê o histórico da conversa).
- `json_schema` (opcional): JSON Schema. Quando presente, é passado ao parâmetro `format` do Ollama (structured output) e a resposta é **JSON validado** contra o schema; quando ausente, retorna texto livre.
- Retorno: `str` (texto, ou JSON serializado quando `json_schema` é usado).

**Config server-side (não exposta ao modelo, via env com defaults):**
- `OLLAMA_HOST` — obrigatório (ex.: `172.19.32.1:11434`).
- `DELEGATE_LOCAL_MODEL` — default `qwen3:8b`.
- `DELEGATE_LOCAL_NUM_CTX` — default `8192`.
- `DELEGATE_LOCAL_TIMEOUT_S` — default `180`.
- `think` fixo em `false` (o campo `reasoning` não-padrão do qwen3 é descartado).

**Descrição do tool** (voltada ao modelo): deve deixar explícito *quando* usar — sub-tarefas volumosas/repetitivas, geração de saída grande, e extração/estruturação — e *quando não* (raciocínio profundo, planejamento, tarefas triviais).

## 4. Registro no opencode

Adicionar ao `opencode.json` (escopo de projeto):

```json
"mcp": {
  "delegate_local": {
    "type": "local",
    "command": ["python3", "mcp/delegate_local/server.py"],
    "enabled": true,
    "environment": {
      "OLLAMA_HOST": "{env:OLLAMA_HOST}"
    }
  }
}
```

O comando roda a partir da raiz do projeto (o repo `jarvis`). `OLLAMA_HOST` é repassado explicitamente.

## 5. Tratamento de erro

Cada falha vira **erro claro do tool** (não crash do processo):

| Situação | Comportamento |
|---|---|
| `OLLAMA_HOST` ausente | erro na inicialização/tool explicando a env faltante |
| Ollama inacessível | erro: "Ollama não respondeu em `<host>`" |
| Timeout (> `DELEGATE_LOCAL_TIMEOUT_S`) | erro com o tempo e dica de cold start |
| `json_schema` inválido | erro de validação antes de chamar o modelo |
| Resposta não-JSON quando `json_schema` pedido | erro (não devolve texto cru como se fosse JSON) |

## 6. Testes

**Unit (rápidos, sem GPU):**
- `ollama_client`: contra um servidor HTTP fake — sucesso, timeout, corpo não-JSON, erro HTTP.
- `server`: `json_schema` inválido → erro; schema válido → passa `format` correto; sem schema → texto livre.

**Integração (lenta, real):**
- Chamada real ao Ollama: `delegate_local("Responda: pong")` → contém `pong`.
- Com `json_schema` (ex.: `{"type":"object","properties":{"n":{"type":"number"}},"required":["n"]}`) → JSON válido e conforme.

**End-to-end (a métrica que importa):**
- Criação do MCP no opencode: `opencode mcp list` (ou equivalente) mostra `delegate_local`.
- `opencode run` pedindo explicitamente o uso do tool em uma tarefa adequada (volumosa) → o tool é **invocado** e retorna.
- **Medir a taxa de invocação** do tool em prompts que deveriam usá-lo (métrica que a Fase 1 deixou em aberto).

## 7. Não-objetivos

- Classifier/semântica de confiança (é a **Fase 2-B**; ganhará tool próprio).
- Voz (C), tela/visão (D), ações no PC (E).
- Execução de qualquer ação: o tool **só faz inferência** — seguro por construção.
- Failover/LiteLLM (adiado).

## 8. Riscos

| Risco | Mitigação |
|---|---|
| Invocação ainda é escolha do modelo (não 100% determinística) | Medir taxa; se baixa, reforçar descrição ou partir p/ plugin |
| Cold start do `qwen3:8b` (>300 s) | Timeout explícito; `keep_alive` no Ollama; documentar |
| Dependência Python no repo | venv isolado + `requirements.txt`; sem impacto no resto |
| `OLLAMA_HOST` muda no reboot | já resolvido dinamicamente no `.bashrc` (Fase 1) |

## 9. Critério de sucesso

O tool `delegate_local` existe, é descoberto pelo opencode, executa inferência no modelo local na GPU, devolve texto/JSON conforme o contrato, e é **invocado pelo menos uma vez** numa tarefa adequada via `opencode run`, com a taxa de invocação medida e registrada.
