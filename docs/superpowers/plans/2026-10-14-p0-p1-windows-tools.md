# P0+P1 — Correções das tools do Windows e base de qualidade (jarvis) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fechar as issues P0/P1 (#19–#29, #32), destravando o uso real das tools do Windows — teclado, texto, visão, arquivos e clipboard — mais a base de CI e diagnóstico, em PRs pequenos e verificáveis.

**Architecture:** Quatro trilhos por área de arquivo (act/teclado+texto+open · visão · winfs/arquivos · win_context/clipboard) + infra (CI, docs), executados em **ondas** que maximizam o paralelismo sem conflito de arquivo. Cada issue = 1 worktree + 1 branch + 1 PR (política do repo); rebase sobre a onda anterior. Um prefactor pequeno (helper de erro, parte da #26) desbloqueia os demais.

**Tech Stack:** Python 3.10 (`voice/`, `mcp_servers/`), TypeScript rodado por Node 24 com type-stripping (`.opencode/`), PowerShell 5.1 via interop WSL→Windows, `pytest` + `node --test`, GitHub Actions.

## Global Constraints

- **1 issue → 1 branch → 1 PR** (CONTRIBUTING); `main` protegida, nada de push direto.
- Testes antes de cada PR: `voice` (317), `delegate_local` (17), `win_context` (12), TS (114) — todos rodam no Linux/WSL.
- Sem segredos nem caminhos pessoais de máquina no código/docs (SECURITY.md).
- Erros de tool padronizados pelo helper `.opencode/lib/tool-error.ts` (criado na Onda 0): mensagem com **etapa + causa + ação**, truncada e **sem ecoar conteúdo sensível**.
- E2E que exige Windows/sessão real não roda no CI: vira **checklist manual no PR**, com evidência colada no comentário da issue.
- Commits no estilo do repo (`fix(act): …`, `feat(winfs): …`, `docs: …`), PT sem acento no assunto quando o histórico já faz assim.
- Prefetches de ambiente: Node 24.18 / Python 3.10.12 (iguais ao local).

## Evidências do recon (2026-10-14) — baseline

| Caminho | Medida / achado | Issue |
|---|---|---|
| `see_screen` | capture 1,48s ✅; serve 0,17s ✗ HTTP 500; run 3,9s ✗ exit 1; total 5,61s. **Causa raiz: modelo `…-vision-exp` não existe mais** | #21 |
| `<modelo> -f png` (probe sintético) | `deepseek-v4.1-flash` → "Vermelho" ✅ · `glm-5.3-flash` → descreveu ✅ · `deepseek-v4-pro` → não aceita imagem ✗ | #21/D2 |
| `act_key` fg | `SendWait('ENTER')` digita literal; `+` = Shift → `ctrl+v` vira "ctrlV" | #19 |
| `act_key` bg | parser próprio espera SendKeys (`{ENTER}`, `^v`) — diverge do fg e da sintaxe natural | #19 |
| `act_type` `\` | builders/PowerShell/SendKeys **preservam**; perda não reproduzível a montante (modelo/JSON?) | #20 |
| Notepad background | `confirmed\|digitado` 3× (incl. repro exato), foco intacto, job UIA 0,6s — **não é regressão** | #28 |
| Windows Terminal background | `unconfirmed\|sem controle de edição` — esperado (ignora WM_CHAR postado) | #28 |
| `win_read` | guard `/mnt/` rejeita WSL; diretório → exit 1 cru; sem listagem | #24 |
| `parseAllowlist` | bug real: `;/` sem espaço não separa (regex compartilha lookahead) | #22 |
| Permissões MCP | tools `win_context_win_*` são **ocultadas** pelo `"*": "deny"` do chat; `ask` é inoperante na voz (run auto-rejeita, serve pendura) | #25 |
| Suites | voice 317 / delegate 17 / win_context 12 / TS 114 — 100% no Linux, nada precisa de skip no CI | #29 |

## Decisões

- **D2 resolvida (probe):** default de visão → `opencode-go/deepseek-v4.1-flash` (aceita imagem; mesmo provider dos demais agentes). Alternativa: `glm-5.3-flash`.
- **D1 (#25)** política da escrita no clipboard — recomendado `allow` + `confirm=true` + SafetyGate de conteúdo (funciona por voz; `ask` não funciona na voz).
- **D3 (#20)** dono fornece o retorno bruto/JSON do teste original (ou aceita instrumentar `JARVIS_ACT_DEBUG` e coletar).
- **D4 (#28)** dono fornece a string completa do repro e confirma reinício do opencode; sem repro, issue fecha como "não reproduzido + causa provável".
- **D5 (#23)** deny explícito de interpretadores (`cmd`, `powershell`, `pwsh`, `wscript`, `cscript`, `mshta`, `rundll32`, `regsvr32`) — confirmar.
- **D6 (#27)** stack de lint: **ruff + Biome** via `scripts/lint.sh` — confirmar.

## Ondas de execução

| Onda | Paralelismo | PRs |
|---|---|---|
| **0 — destrave** | 3 PRs paralelos | #21 visão · PR-0 helper de erro (#26) · #29 CI |
| **1 — correções principais** | 4 PRs paralelos (arquivos disjuntos) | #19 act_key · #24 win_read · #25 clipboard/chat · #32 DIAGNOSTICS |
| **2 — dependentes** | 2 trilhos (act serial; winfs) | #23 → #20 → #28 (serial no trilho act) · #22 (winfs) |
| **3 — fechamento** | 2 PRs serial | #26 varredura final · #27 lint/format baseline |

Conflitos previstos e tratados: `opencode.json` (#21 → #25), `act-tools.ts` (#19 → #23 → #20 → #28), `winfs.ts` (#24 → #22), `hook.ts` (#25 → #23). Regra: só abre a branch seguinte após o merge da anterior.

---

## Onda 0

### Task 1 — #21 `see_screen`: modelo válido + erro com causa real

**Arquivos:** `voice/config.py` (default `vision_model`), `opencode.json` (agente `vision`), `voice/vision.py` (erro), `voice/tests/test_vision.py`, comentário na issue #21.

- [ ] Teste que falha em `voice/tests/test_vision.py`: serve devolve 500 e run falha com stderr ANSI → mensagem final contém a etapa (`serve`) e a causa do run, sem ANSI.
- [ ] Trocar o ID do modelo nos dois lugares para `opencode-go/deepseek-v4.1-flash` (D2).
- [ ] `vision.py`: não engolir o erro do serve quando o run também falhar (agregar causas por etapa); `strip ANSI` antes de truncar.
- [ ] `cd voice && .venv/bin/python -m pytest -q` → 317+ verdes.
- [ ] E2E: `./jarvis --see-text "benchmark de diagnostico"` → exit 0 com descrição; medir duração e colar no PR/issue.
- [ ] PR `fix(vision): modelo de visao valido e erro com causa real (#21)`.

**Est:** P · **Risco:** baixo (modelo validado por probe).

### Task 2 — PR-0 (parte da #26): helper de erro compartilhado

**Arquivos:** criar `.opencode/lib/tool-error.ts` e `.opencode/lib/tool-error.test.ts`.

- [ ] Testes que falham: `truncate` (≤400 + "(truncado)"); `redact` (sk-/ghp_/AKIA/Bearer → `[REDACTADO]`); `extractCause` com `{exitCode, stderr}`, ANSI, e `Error` simples; `formatToolError` no formato `erro em <tool> (etapa: <step>): <causa>`.
- [ ] Implementar:

```ts
export type ErrorContext = { tool: string; step: string; detail?: string; action?: string };
export function extractCause(err: unknown): string;      // exitCode+stderr > message; strip ANSI; truncar 400
export function formatToolError(ctx: ErrorContext, cause: unknown): string;
```

- [ ] `node --test .opencode/lib/tool-error.test.ts` → verde.
- [ ] PR `feat(lib): helper de erro com causa real (prefactor da #26)` (parte da #26; a varredura fecha na Onda 3).
- [ ] Convenção de uso nos trilhos: plugins capturam o erro do shell e **retornam** `formatToolError(...)` (consistente com os status `erro: …`/`recusado: …` já usados).

**Est:** P · **Risco:** baixo.

### Task 3 — #29 CI: testes em todo PR

**Arquivos:** criar `.github/workflows/ci.yml`; `mcp_servers/win_context/requirements-dev.txt` (adicionar `-r requirements.txt`); `CONTRIBUTING.md` (comandos dos 4 suites); `scripts/protect-main.sh` (nota: não zerar checks ao re-rodar).

- [ ] Workflow com 4 jobs (`actions/checkout@v6`, `setup-python@v7`, `setup-node@v6`): `pytest voice` (3.10.12), `pytest delegate_local`, `pytest win_context`, `node --test` (24.18.0) em `.opencode`; `cache: pip|npm`; `concurrency` com cancel; `permissions: contents: read`.
- [ ] Sem skips: nenhum teste depende de Windows/áudio (verificado).
- [ ] PR; acompanhar 1º run; ajustar (ex.: se `faster_whisper` faltar, instalar `-r requirements.txt` no job voice).
- [ ] Após verde: marcar os 4 checks como obrigatórios (gh api/UI) e atualizar `protect-main.sh` para preservá-los.

**Est:** P/M · **Risco:** baixo.

---

## Onda 1

### Task 4 — #19 `act_key`: sintaxe natural + envio de teclas de verdade

**Arquivos:** criar `.opencode/act/keys.ts` + `keys.test.ts`; `ps.ts`; `win.ts`; `plugins/act-tools.ts`; testes existentes.

- [ ] Parser natural (case-insensitive): `enter esc tab backspace delete space up down left right home end pgup pgdn f1..f24`, letras/dígitos, `plus`; combos `ctrl+ alt+ shift+ win+` (múltiplos: `ctrl+shift+esc`); acordes separados por espaço/vírgula; desconhecido → erro didático com exemplos.
- [ ] FG: trocar `SendKeys` cru por `keybd_event` (P/Invoke, mesmo padrão do `act_click`): mods down → tecla → mods up. `win+r` passa a funcionar em foreground (validar E2E).
- [ ] BG: `PostMessage WM_KEYDOWN/UP` com lParam correto (scan code `MapVirtualKey` + flag extended); sem foco. Limitações documentadas: combos com Ctrl/Alt best-effort; `win+r` **impossível** em background (hotkey do sistema).
- [ ] Testes: parser (tabela de casos), encoders FG/BG, invariante sem `SetForegroundWindow/SetCursorPos`, descrição da tool atualizada.
- [ ] E2E checklist: Notepad fg `ctrl+v` (com clipboard preparado), `ctrl+s`, `win+r`; Notepad bg `enter`/`tab`.
- [ ] PR `fix(act): act_key com sintaxe natural e teclas de verdade (#19)`.

**Est:** M · **Risco:** médio (varia por app; mitigado por E2E + docs).

### Task 5 — #24 `win_read`: ler WSL + listar diretórios

**Arquivos:** `.opencode/act/winfs.ts`; `plugins/winfs-tools.ts`; `winfs.test.ts`; `winfs-tools.test.ts`.

- [ ] Roteamento por forma do caminho: `/mnt/<letra>/…` → PowerShell; absoluto Unix (WSL) → `fs` nativo (mesmo contrato de retorno).
- [ ] Script Windows combinado (stat→read|list) com sentinelas `JARVIS-ERR:<code>` e exit 0: arquivo → conteúdo; dir → JSON-lines `{"name","type","size"}`; listagem WSL no mesmo shape; cap ~200 + "…N omitidas".
- [ ] Erros claros: inexistente / sem permissão; descrição da tool corrigida (hoje promete "WSL ou Windows" e não cumpre).
- [ ] Testes: roteamento, sentinelas, parser da listagem, cap, regressão do guard.
- [ ] E2E: ler arquivo do repo (`/home/...`), listar repo, listar `C:\Windows`, inexistente → erro claro.
- [ ] PR `fix(winfs): win_read le WSL e lista diretorios (#24)`.

**Est:** M · **Risco:** médio-baixo.

### Task 6 — #25 clipboard + contexto Windows no `chat`

**Arquivos:** `mcp_servers/win_context/context.py`, `server.py`, `tests/`, `README.md`; `opencode.json`; `.opencode/safety/hook.ts` (+ teste).

- [ ] `win_clipboard_write(text, confirm=false)`: exige `confirm=true`; texto em **base64 UTF-8** no script (`Set-Clipboard`), eliminando injeção/quoting/Unicode.
- [ ] `opencode.json` (chat): após `"*": "deny"`, allow explícito das 5 tools (`win_context_win_list_text`, `_win_tree_text`, `_win_clipboard_text`, `_win_processes_text`, `_win_clipboard_write`) — nomes exatos, ordem importa (última regra vence) — e prompt atualizado (usar texto em vez de imagem quando possível; só escrever clipboard a pedido; não ler clipboard sem pedido).
- [ ] SafetyGate: mapping `win_context_win_clipboard_write` → `clipwrite` (conteúdo passa por DENY/CREDENTIAL).
- [ ] Testes: pytest MCP (recusa sem confirm; roundtrip Unicode no base64; texto não aparece cru no script) + node (mapping; `rm -rf /` bloqueado).
- [ ] E2E: reiniciar opencode; `opencode run --agent chat "quais janelas estão abertas?"` sem auto-reject; escrita controlada com texto combinado.
- [ ] PR `feat(win-context): clipboard no chat + escrita gateada (#25)`.

**Est:** P · **Risco:** político (D1) — implementar conforme decisão.

### Task 7 — #32 `DIAGNOSTICS.md`

**Arquivos:** criar `docs/DIAGNOSTICS.md`; `README.md` (link + enxugar "Limitações conhecidas" apontando pro doc).

- [ ] Estrutura: como diagnosticar (logs do overlay `%LOCALAPPDATA%\jarvis\brain.log`, `--once`, `--see-text`, `--list-mics`), template de limitação (sintoma/repro/causa/workaround/issue), seções por área (act_*, winfs, win_*, visão, áudio/loop), como reportar.
- [ ] Conteúdo inicial com os fatos do recon: Terminal bg (esperado), Notepad echo/restore + latência PS ~11s, `win_write` allowlist (precedência `local.conf` → loop → opencode; restart), UIA vazia em Electron, timeout UIA ~5s, `see_screen` caro (preferir win_context), limitações de `act_key` bg.
- [ ] Entradas das issues desta onda ficam com status "corrigido na #X" conforme os merges.
- [ ] PR `docs: DIAGNOSTICS.md com limitacoes conhecidas das tools (#32)`.

**Est:** P · **Risco:** baixo.

---

## Onda 2

### Task 8 — #23 `act_open` com argumentos (com gate)

**Arquivos:** `ps.ts`, `plugins/act-tools.ts`, `.opencode/safety/rules.ts`/`hook.ts` (+ testes).

- [ ] Schema `act_open { target, args?: string[] }`; builder cota com regras Windows (porte validado do `list2cmdline`) e emite `Start-Process -FilePath '<target>' -ArgumentList <linha>`.
- [ ] SafetyGate: DENY explícito de interpretadores (D5) e regras existentes sobre o comando completo; URL/app sem args inalterados.
- [ ] Testes: snapshots de quoting (espaços, aspas, `\` final, `%`), denies.
- [ ] PR `feat(act): act_open aceita argumentos com gate (#23)`.

**Est:** M · **Risco:** médio (segurança — deny conservador).

### Task 9 — #22 `win_write`: allowlist documentada + fix do parser

**Arquivos:** `.opencode/act/winfs.ts` (regex), `plugins/winfs-tools.ts` (mensagem), `README.md`, testes.

- [ ] Fix `parseAllowlist`: separador `;`/`:` sem compartilhar lookahead (regressão: `"/a;/b"` sem espaço → 2 itens).
- [ ] Recusa instrutiva: como configurar `JARVIS_WIN_ALLOW_WRITE` (exemplo), restart necessário, aviso "não aponte o drive inteiro".
- [ ] README: subseção "Allowlist de escrita" (cadeia `local.conf` → loop → opencode; precedência).
- [ ] E2E: escrita + append em dir autorizado; recusas (vazio/fora/sem confirm).
- [ ] PR `docs(winfs): allowlist de escrita documentada + fix do parser (#22)`.

**Est:** P/M · **Risco:** baixo.

### Task 10 — #20 `act_type`: barras invertidas (instrumentar + regressão)

**Arquivos:** `plugins/act-tools.ts` (instrumentação sob env), `ps.ts`/`win.ts` (se fix local necessário), testes, `docs/DIAGNOSTICS.md`.

- [ ] Testes de regressão codificando o contrato dos builders: `\`, aspas, `%` chegam íntegros aos scripts FG/BG.
- [ ] Instrumentação opt-in (`JARVIS_ACT_DEBUG=1`) logando os **args brutos** recebidos pelo `execute` (sem conteúdo sensível por default? só quando ligado) para capturar a origem da perda.
- [ ] Com o dado do dono (D3): se a perda é a montante (JSON do modelo/transcrição) → entrada no DIAGNOSTICS + orientação; se local → fix + teste de regressão.
- [ ] PR `fix(act): act_type preserva barras invertidas — regressao + diagnostico (#20)`.

**Est:** P (nosso lado) / M (investigação) · **Risco:** médio de "fix no lugar errado".

### Task 11 — #28 mensagens por causa (e fechamento)

**Arquivos:** `plugins/act-tools.ts`; `.opencode/act/win.ts` (opcional: código de razão no `JARVIS_RESULT`); `docs/DIAGNOSTICS.md`.

- [ ] Distinguir as 3 causas de `unconfirmed`: `noset` → "não expõe controle de edição (típico de terminais); quer que eu traga para frente?"; `set` → "texto enviado, sem confirmação da UIA"; `timeout` → "não respondeu em 5s; tente de novo". Nunca afirmar "recusou" sem saber.
- [ ] Testes das 3 mensagens.
- [ ] Com o dado do dono (D4): registrar conclusão (provável sessão antiga/transiente); atualizar DIAGNOSTICS; fechar issue.
- [ ] PR `fix(act): mensagens por causa na injecao em background (#28)`.

**Est:** P (mensagens) · **Risco:** baixo.

---

## Onda 3

### Task 12 — #26 varredura final dos erros

**Arquivos:** `act-tools.ts`, `winfs-tools.ts`, `see-tools.ts`, `mcp_servers/win_context/context.py`, testes.

- [ ] Aplicar `formatToolError` em todos os call sites restantes (10 mapeados: act-tools ×7, winfs ×2, see ×1) — cada trilho já aplicou nos seus; conferir e completar.
- [ ] Alinhar `win_context/context.py` ao formato (etapa: powershell) + redação.
- [ ] Matriz de verificação: simular falha em cada tool e conferir mensagem útil (testes).
- [ ] PR `feat(tools): erro real com causa em todas as tools (#26)` — fecha a issue.

**Est:** M · **Risco:** baixo.

### Task 13 — #27 lint + formatter baseline

**Arquivos:** `ruff.toml` (raiz), `.opencode/biome.json`, `.opencode/package.json` (+lock), `requirements-dev.txt` (raiz, ruff pinado), `scripts/lint.sh`, formatação em massa, `CONTRIBUTING.md`/`README.md`.

- [ ] Configs e script (D6): `ruff check`+`format` (Python) e `biome check` (TS); `--fix` opcional.
- [ ] Aplicar formatação em commits separados ("adota tooling" → "aplica formatação").
- [ ] Documentar comando único nos guias.
- [ ] PR `chore(quality): adota ruff + biome com comando unico (#27)`.

**Est:** M · **Risco:** baixo (diff grande, mecânico; roda por último para não conflitar).

---

## Execução

- Uma **worktree por issue** (`git worktree add .worktrees/<issue> -b fix/<issue> main`), adicionar `.worktrees/` ao `.gitignore` se faltar.
- Cada task: TDD (teste falha → implementa → verde) → suíte completa → E2E checklist quando aplicável → PR.
- Entre tasks, **revisão de duas etapas** (spec + qualidade) antes de abrir o PR (subagent-driven-development).
- Issues #30/#31 (CI lint/tipos, pre-commit) ficam para depois — dependem da #27/#29 e não são P0/P1.
