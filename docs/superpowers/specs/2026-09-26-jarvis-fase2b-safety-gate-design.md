# Jarvis Fase 2-B — SafetyGate determinístico (Design)

- **Data:** 2026-09-26
- **Status:** proposta (revisão)
- **Fase:** 2-B. Depende da Fase 1 e 2-A (ambas em `main`).
- **Nota de escopo:** esta fase **adia** o classificador aprendido (ver §7) e entrega o **SafetyGate determinístico**, que era previsto para a Fase E. Justificativa em §1.

---

## 1. Contexto e por que o foco mudou

O objetivo final é um agente acionado por **voz** que **executa qualquer coisa no computador**. Isso só é seguro com um **gate de ações** confiável — e voz/transcrição erra, então o gate é pré-requisito, não enfeite.

A pesquisa da Fase 2-B apontou:
- Um **classificador encoder leve** (SetFit/MiniLM, ~90–300 MB, ms/CPU) é ~10–50x mais leve que um LLM (§8) — **não** é "pesado como LLM". Mas…
- Os hooks de plugin do opencode **não permitem rotear modelo por mensagem** (o `model` só aparece como *input* em `chat.message`/`chat.params`). O que dá de determinístico é **gating**: `permission.ask` (`allow|ask|deny`) e `tool.execute.before`.
- Logo, um classificador **aprendido** não tem ponto determinístico de alto valor hoje; **para segurança, regras determinísticas são superiores** (auditáveis, instantâneas, sem treino).

**Conclusão:** Fase 2-B entrega o **SafetyGate determinístico (rules-first)** via `permission.ask`. O classificador aprendido fica adiado (§7).

## 2. Arquitetura

```
ação (tool/permissão no opencode)
   │
   ▼
plugin .opencode/plugins/safety-gate.ts
   │  hook: permission.ask
   ▼
motor de regras (rules.ts)  → allow | ask | deny
```

- **Determinístico primeiro:** o motor de regras decide. Sem modelo no caminho crítico.
- **Conservador por padrão:** o que não casa com allowlist/denylist vira `ask` (nunca `allow` silencioso para desconhecido).

### Estrutura de arquivos (nova)

```
.opencode/
  package.json                 # dependência @opencode-ai/plugin + tooling de teste
  plugins/safety-gate.ts       # registra o hook permission.ask
  safety/
    rules.ts                   # motor de regras puro (sem dependência do opencode)
    rules.test.ts              # testes do motor
  README.md                    # como testar e o que o gate cobre
```

**Fronteiras:**
- `rules.ts`: função pura `decide(action) -> {status, reason}`. Não conhece o opencode. Testável isoladamente.
- `safety-gate.ts`: só liga o hook ao motor. Sem lógica de decisão.

## 3. Contrato do motor de regras

```
type Decision = { status: "allow" | "ask" | "deny"; reason: string }
decide(input: { tool: string; command?: string; path?: string; args?: unknown }): Decision
```

**Ordem de avaliação (a primeira que casar vence):**
1. **deny** — padrões claramente destrutivos/irreversíveis:
   - `rm -rf /` e variantes de raiz/home, `mkfs*`, `dd if=… of=/dev/*`, `:(){:|:&};:`
   - sobrescrever disco/boot, `dd` para device de bloco
   - ler/exfiltrar credenciais (`~/.ssh`, `.env`, `~/.aws`, tokens) para fora
2. **ask** — ações sensíveis mas legítimas:
   - `sudo`, `git push --force`, `git reset --hard`, `chmod 777`, `chown -R`, `curl|sh`/`wget|sh`
   - escrita fora do worktree (`external_directory`), remoção recursiva dentro do projeto
   - qualquer comando não reconhecido
3. **allow** — allowlist explícita de leitura/comandos seguros:
   - leitura (`read`, `glob`, `grep`, `list`), `git status|diff|log`, `ls`, `pwd`, etc.

## 4. Integração no opencode

Plugin de projeto em `.opencode/plugins/safety-gate.ts`, carregado automaticamente (documentado em `.opencode/README.md`). Registra:

```ts
"permission.ask": async (input, output) => {
  const d = decide({ tool: input.tool ?? "unknown", command: input.command, path: input.path, args: input.args })
  output.status = d.status
}
```

(Os campos exatos de `Permission` serão confirmados nos tipos `@opencode-ai/plugin` durante a implementação.)

## 5. Tratamento de erro

| Situação | Comportamento |
|---|---|
| entrada inesperada/ambígua | `ask` (conservador) |
| erro no motor de regras | `ask` (fail-safe), logado via `client.app.log` |
| hook indisponível | opencode usa o default dele (não quebra) |

## 6. Testes

- **Unit (`rules.test.ts`)**: uma bateria de casos por categoria — destrutivos → `deny`; sensíveis → `ask`; leitura → `allow`; desconhecido → `ask`. Rodável com `bun test` (ou o runner que o `.opencode` usar).
- **Integração manual**: provocar uma permissão de `bash` com um comando destrutivo e confirmar que o gate responde `deny`; com um comando de leitura e confirmar `allow`.

## 7. Adiado (com justificativa)

- **Classificador aprendido (encoder/SetFit)**: sem gancho determinístico de alto valor. Fica para quando (a) houver um uso de classificação **difusa** que regras não cubram, ou (b) adotarmos o **pré-router no LiteLLM**. Enquanto isso, regras cobrem segurança.
- **Roteamento determinístico nuvem↔local**: só via proxy (LiteLLM) — decisão separada (LiteLLM foi adiado na Fase 1).
- Voz (C), tela/visão (D), o restante de ações no PC (E).

## 8. Pesquisa registrada (peso das alternativas ao JEV)

| Abordagem | Peso | Latência | Veredito |
|---|---|---|---|
| Encoder (`all-MiniLM-L6-v2` 22,7M / `ModernBERT-base` 149M) | ~90–600 MB | ms, CPU | leve ✅ |
| SetFit (few-shot) | ~110–355M | treino s, inferência ms | leve ✅ |
| LLM-as-classifier (`delegate_local`, qwen3:8b) | ~5 GB | ~1–2 s, GPU | **pesado** ❌ |

Fontes: blog SetFit (HF), blog ModernBERT (Answer.AI/LightOn).

## 9. Critério de sucesso

O plugin `safety-gate` está ativo; uma ação destrutiva é **negada**, uma sensível vira **ask**, e uma leitura é **permitida** — tudo por regras determinísticas, com testes unitários cobrindo as três categorias.
