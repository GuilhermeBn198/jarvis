# Backlog — jarvis

Itens registrados para atacar depois, com contexto.

## 1. Otimizar a latência da resposta (voz) — PRIORIDADE: média
**Contexto:** já houve ganho grande (baseline `run`+`sapi` ~20s → `serve`+`piper` ~4,8s; agente `chat` ~2,1s vs `build` ~6,8s), mas ainda incomoda um pouco.

**Números medidos:**
- turno conversacional (`chat`, serve quente): **~2,1 s**
- turno com `run` (startup): ~16 s
- visão (`--see`, usa `run`): **~29 s** (dominado pelo startup do `run`)

**Ideias a investigar (quando atacarmos):**
- [x] Usar `serve` também no caminho de **visão** — FEITO: **4,8s vs 11,5s** (−58%); `vision.see` usa serve com fallback para `run`.
- [x] Reduzir o contexto/system prompt do agente `chat` (tools off) — TESTADO: **sem ganho** (1,84 vs 1,85s, n=8) → revertido; o gargalo não são as tools listadas.
- [x] Streaming: começar a falar (TTS por sentença) enquanto o texto é gerado — FEITO (spec `docs/superpowers/specs/2026-09-29-jarvis-streaming-tts-design.md`, plano `docs/superpowers/plans/2026-09-29-jarvis-streaming-tts.md`). Medido: 1º pedaço em ~3,9s vs resposta completa ~4,2s.
- [x] Testar modelos mais rápidos para conversa (ex.: `opencode-go/gpt-6-luna`) — medido igual (~6,6–9,2s); **não** ajuda (gargalo é overhead, não geração).
- [x] Medir com `bench.py` antes/depois — `bench.py` agora mede agente (run/serve) + TTS + visão.

**Números atuais (medidos):** conversa `chat` via serve quente **~1,4–2,1s**; visão via serve **~3–5s**; TTS Piper ~1,1s.

## 2. Robustez de entrada de voz (feito nesta rodada)
- [x] Whisper alucinando em silêncio (ex.: transcreveu `'1, 2, 1'`/"101") → habilitar **VAD** + anti-hallucination no `faster-whisper`.
- [x] "Não espera eu terminar de falar" (janela fixa de 5s) → **push-to-talk** (Enter inicia/para).

## 3. Roteamento determinístico nuvem↔local — adiado
- Plugin do opencode não permite trocar modelo por mensagem; exigiria **proxy (LiteLLM)** com pré-router. Adiado (LiteLLM foi adiado na Fase 1).

## 4. Classificador aprendido — adiado
- Sem gancho determinístico de alto valor; regras do SafetyGate cobrem segurança. Reavaliar com proxy/routing.

## 5. Fase E — ações no PC — FEITO
- [x] Custom tools `act_*` (digitar/teclas/clicar/abrir) + agente `act` + gate (regras Windows) + `--do` na voz.

## 6. Indicador visual de estado (avatar / GUI) — PRIORIDADE: alta (UX)
**Problema:** uma vez iniciado, o jarvis roda em segundo plano e **não há como saber** se está **ouvindo**, **pensando/processando** ou **agindo no PC**. Deixar o terminal com os logs à mostra **não é opção**.

**Objetivo:** um sinal visual **discreto e sempre visível** refletindo o estado em tempo real.

**Estados a sinalizar** (máquina de estados do `voice_loop`):
`idle` (aguardando) · `listening` (gravando / VAD detectou fala) · `transcribing` (STT) · `thinking` (agente/LLM) · `speaking` (TTS) · `acting` (ações no PC) · `error`.

**Opções de renderização (Windows):**
- **A) Ícone na bandeja (tray)** — leve, sem janela; cor/ícone por estado (`NotifyIcon` via PowerShell/.NET). *(recomendado p/ v1)*
- **B) Overlay flutuante** — bolinha sempre-no-topo num canto; janela minúscula `always-on-top` (Tkinter/PowerShell WPF; Tauri/Electron depois).
- **C) Avatar animado** (GIF/Live2D/VRM) — mais estético, mais peso; fase futura.

**Integração (loop no WSL → GUI no Windows):**
- O `voice_loop` emite as transições de estado; a GUI (processo **separado no Windows**) lê. Opções, da mais simples:
  - **arquivo de estado** `state.json` em caminho visível (`/mnt/c/...`) lido por *polling* (~200ms); ou
  - **endpoint HTTP local** minúsculo (push via SSE).
- A GUI **não** é o terminal; roda à parte, sempre visível.

**Notas:** não logar áudio/imagem (só o rótulo de estado); o `convlog`/timings seguem para diagnóstico, mas o estado é efêmero.

**Como rodar (v1):**
- Cérebro (WSL): `cd voice && . .venv/bin/activate && python loop.py --voice` (o `StateHub` sobe em `127.0.0.1:8765`; env `JARVIS_STATE_PORT`, `JARVIS_REQUIRE_GUI`).
- Overlay (Windows): `cd gui/src-tauri && cargo run` (Tauri 2, frontend estático embutido, **sem Node**; requer Rust + MSVC Build Tools + WebView2). O menu tem "Iniciar/Reiniciar cérebro" (sobe o loop via `wsl.exe`).

**Fases:** v1 = **overlay/orbe + SSE** → FEITO (spec `docs/superpowers/specs/2026-09-28-jarvis-state-indicator-design.md`, plano `docs/superpowers/plans/2026-09-28-jarvis-state-indicator.md`; GUI em `gui/`) → v2 = reativo ao áudio → v3 = avatar animado.
**Contexto de janelas — FEITO via 7.B (2026-10-04):** listar janelas ativas e capturar o conteúdo deixou de ser TODO — o MCP `win_context` expõe `win_list_text` (janelas), `win_tree_text` (conteúdo UIA por janela), `win_clipboard_text` e `win_processes_text`. Ver 7.B.

## 7. Experiência no Windows — iniciativa em 3 sub-projetos (2026-10-01)
Dor: (1) o Jarvis só age na **janela em foco** (bloqueia o usuário); (2) para "ver" a tela ele **sempre tira print** (custo de tokens); (3) editar arquivos do Windows acabou sendo feito **digitando em terminal, às cegas** (fora do escopo de `edit`/`write`, que ficam na raiz do repo).
Ordem e relação: **A → B → C**, com um alicerce comum (descoberta de janelas / HWND).

### 7.A — Ações Windows não intrusivas (background) — FEITO (2026-10-01); foco/cursor verificados E2E (2026-10-05)
Spec: `docs/superpowers/specs/2026-10-01-jarvis-windows-background-actions-design.md`.
Resumo: `win_list` (título/processo/HWND); `act_type`/`act_key` com modo **background** opt-in (foreground segue padrão); injeção de texto via `EM_SETSEL` (caret) + `WM_CHAR` (`PostMessage`), com a UIA só **localizando e verificando** (nunca `SetValue`); resolve alvo por título/processo (ambíguo ⇒ candidatos); **verifica e pede consentimento** se a janela ignorar background (nunca rouba foco). Não-objetivo: clicar por elemento (v2).
Verificação automática (read-only) do `win_list` real passou em 2026-10-01: `powershell.exe -NoProfile -EncodedCommand` retornou JSON-lines com `hwnd`/título/processo de janelas abertas. Injeção E2E no **Notepad em segundo plano** verificada em 2026-10-05 (ver bloco "E2E de foco/cursor — #9"). **Pendente:** o caminho de consentimento (app que ignora entrada em background, ex. Chrome/Electron → esperado `unconfirmed`) e a injeção de **teclas** (`act_key`) ainda não foram verificados E2E.

**Verificação E2E parcial (2026-10-04):** rodada numa sessão Windows real (Notepad moderno/WinUI). Achou e corrigiu um **bug**: o editor do Notepad novo é `ControlType.Document` (classe `RichEditD2DPT`), não `ControlType.Edit`; o script procurava só `Edit` e caía no fallback inerte (`[I3]`), retornando `unconfirmed`. Agora procura `Document` antes de `Edit` e a injeção em background retorna **`confirmed`** com o texto entrando de fato. O invariante de código (script de background sem `SetForegroundWindow`/`SetCursorPos`/`mouse_event`) segue coberto por teste. **Ressalva:** a medição de foco/cursor ficou inconclusiva — a máquina estava em uso em paralelo (foco e cursor mudando entre leituras), então a garantia "foco/cursor intactos" ainda não foi provada E2E; falta repetir numa sessão ociosa.

**Pendências do review final — RESOLVIDAS (2026-10-04):**
- **[I1] Timeout na UIA** — FEITO: a UIA roda num job com `Wait-Job -Timeout 5`; estouro vira `unconfirmed|UIA timeout`. Cobre `AutomationElement.FromHandle`/`FindFirst`/`SetValue`.
- **[I3] Fallback `WM_CHAR`** — FEITO: o fallback agora mira o **handle nativo do controle** (`NativeWindowHandle` do Document/Edit), não o HWND de topo.
- **[I2] `ValuePattern.SetValue`** — FEITO: `act_type` ganhou `append=true` (concatena ao valor atual); default segue substituindo. **Superado em 2026-10-05:** o `SetValue` foi removido por roubar o foco (ver E2E abaixo); a injeção passou a usar `EM_SETSEL` + `WM_CHAR` via `PostMessage`.

**E2E desta rodada (2026-10-04):** injeção em background confirmada de verdade no Notepad moderno (`confirmed|digitado`); `insert` gravou `AAA` e `append` resultou `AAABBB` (lido do UIA). **Limitação de medição:** a sessão `powershell.exe` do WSL é **não-interativa** — `GetForegroundWindow()` retorna 0 e `GetCursorPos()` retorna 0,0, então foco/cursor **não são mensuráveis** por aqui. A garantia de "não roubar foco/cursor" fica por conta do invariante de código (sem `SetForegroundWindow`/`SetCursorPos`/`mouse_event`, coberto por teste) — a medição E2E exige sessão interativa (issue #9 continua aberta com essa ressalva).

**E2E de foco/cursor — #9 FECHADO (2026-10-05):** numa sessão Windows ociosa (terminal em foco, Notepad em 2º plano), medi `GetForegroundWindow()`/`GetCursorPos()` antes e depois de `act_type` background. O `powershell.exe` do WSL **é interativo** aqui (`UserInteractive=True`, `SessionId=1`), ao contrário da ressalva anterior. Achado: **o `ValuePattern.SetValue` roubava o foco** — medido dentro do script, `FG` saltava do terminal para o Notepad exatamente na chamada `SetValue` (o invariante de "sem `SetForegroundWindow`/`SetCursorPos`/`mouse_event`" não bastava: a UIA ativa a janela). **Correção:** a injeção agora é `EM_SETSEL` (posiciona o caret; `(-1,-1)`=fim p/ append, `(0,-1)`=seleciona tudo p/ substituir) + `WM_CHAR` via `PostMessage` no handle nativo do controle; a UIA fica só para **localizar e verificar** (nunca `SetValue`). Evidência: `append` → FG `20187676`→`20187676`, cursor `1464,576`→`1464,576`, `confirmed`, texto no fim; `replace` → `confirmed`, valor substituído, e `EM_SETSEL(0,-1)+WM_CHAR` medido com FG/cursor idênticos. Testes TS cobrem "nunca chama `SetValue`". Obs.: a tool `act_type` só usa o código novo após **reiniciar o opencode** (o plugin é carregado no início da sessão).

### 7.B — Contexto do Windows via MCP (texto, não imagem) — FEITO (2026-10-04)
MCP `mcp_servers/win_context`: `win_list_text` (janelas), `win_tree_text(hwnd, max_nodes)` (árvore UIA), `win_clipboard_text`, `win_processes_text(filter)`. Reusa a descoberta de janelas do `win_list`. Registrado em `opencode.json`. `see_screen` vira fallback para o que a UIA não expõe (Electron/jogos/canvas — verificado: VS Code devolve árvore vazia).

### 7.C — Arquivos do Windows estruturados — FEITO (2026-10-04)
Fim do "terminal com insert às cegas". Escolha: **(c2) tools dedicadas** `win_read`/`win_write` (via `/mnt/c`), gateadas — mais auditável que expandir o escopo de `edit`/`write` do opencode. **Política de escrita (decidida antes de implementar):** leitura livre (o SafetyGate já nega credenciais via `winread`); escrita exige `confirm=true` **e** o caminho dentro da allowlist `JARVIS_WIN_ALLOW_WRITE` (default vazio = nada autorizado); `winwrite` nunca é `allow` automático (cai em `ask`); destrutivo/credencial continuam `deny`. `append=true` concatena. Helpers puros em `.opencode/act/winfs.ts`; tools em `.opencode/plugins/winfs-tools.ts`.
E2E (2026-10-04): read/write/append reais em `/mnt/c/Users/<voce>/...` funcionaram; caminho fora da allowlist foi recusado. Sem abrir editor/terminal.

**Wake word + gatilhos de frase — FEITO (2026-10-05):** ver spec `docs/superpowers/specs/2026-10-05-jarvis-wake-word-e-triggers-design.md` e plano `docs/superpowers/plans/2026-10-05-jarvis-wake-word-e-triggers.md`. Ativação `free|wake`, registry `triggers.json` (fuzzy, merge por `name`), dispatch para agentes/ações; `VISION_TRIGGER` continua honrado.
**Pendências (deferidas):** (a) verificação **runtime** do overlay — salvar "wake" e conferir `settings.json` (exige humano rodando o GUI); (b) evolução: **gate acústico** opcional antes do STT (spec §7); (c) Minors triados no review: `normalize` não cobre não-ASCII residual, `measure` não emite `idle` com `hub=None`, convlog não registra o agente roteado.
