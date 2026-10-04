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
TODO - Ver contexto dos programas abertos no Windows: listar janelas ativas e capturar o conteudo de cada uma, nao so a janela em foco. Ja da para listar via Get-Process MainWindowTitle. Falta capturar o conteudo e expor como ferramenta do agente.

## 7. Experiência no Windows — iniciativa em 3 sub-projetos (2026-10-01)
Dor: (1) o Jarvis só age na **janela em foco** (bloqueia o usuário); (2) para "ver" a tela ele **sempre tira print** (custo de tokens); (3) editar arquivos do Windows acabou sendo feito **digitando em terminal, às cegas** (fora do escopo de `edit`/`write`, que ficam na raiz do repo).
Ordem e relação: **A → B → C**, com um alicerce comum (descoberta de janelas / HWND).

### 7.A — Ações Windows não intrusivas (background) — FEITO (2026-10-01); injeção E2E pendente de verificação manual
Spec: `docs/superpowers/specs/2026-10-01-jarvis-windows-background-actions-design.md`.
Resumo: `win_list` (título/processo/HWND); `act_type`/`act_key` com modo **background** opt-in (foreground segue padrão); injeção híbrida UIA `ValuePattern` → fallback `PostMessage`; resolve alvo por título/processo (ambíguo ⇒ candidatos); **verifica e pede consentimento** se a janela ignorar background (nunca rouba foco). Não-objetivo: clicar por elemento (v2).
Verificação automática (read-only) do `win_list` real passou em 2026-10-01: `powershell.exe -NoProfile -EncodedCommand` retornou JSON-lines com `hwnd`/título/processo de janelas abertas. Injeção E2E (Notepad em segundo plano + consentimento do Chrome) permanece pendente de verificação manual.

**Verificação E2E parcial (2026-10-04):** rodada numa sessão Windows real (Notepad moderno/WinUI). Achou e corrigiu um **bug**: o editor do Notepad novo é `ControlType.Document` (classe `RichEditD2DPT`), não `ControlType.Edit`; o script procurava só `Edit` e caía no fallback inerte (`[I3]`), retornando `unconfirmed`. Agora procura `Document` antes de `Edit` e a injeção em background retorna **`confirmed`** com o texto entrando de fato. O invariante de código (script de background sem `SetForegroundWindow`/`SetCursorPos`/`mouse_event`) segue coberto por teste. **Ressalva:** a medição de foco/cursor ficou inconclusiva — a máquina estava em uso em paralelo (foco e cursor mudando entre leituras), então a garantia "foco/cursor intactos" ainda não foi provada E2E; falta repetir numa sessão ociosa.

**Pendências do review final (diferidas, não bloqueiam o merge):**
- **[I1] Timeout na UIA** (spec §4 pedia ~3–5s): hoje `AutomationElement.FromHandle`/`FindFirst`/`SetValue` não têm timeout — uma janela travada pode bloquear a tool. Envolver o bloco UIA em job com `Wait-Job -Timeout` e tratar como `unconfirmed`. Não implementado por não ser validável em host real nesta rodada.
- **[I3] Fallback `WM_CHAR`** posta no HWND de topo (não no controle de edição): quase inerte; errar para `unconfirmed` é seguro. Documentado no README.
- **[I2] `ValuePattern.SetValue`** substitui o valor do campo (não insere no cursor) — documentado no README; verificar se vale uma variante "append".

### 7.B — Contexto do Windows via MCP (texto, não imagem) — BACKLOG
Tool MCP que devolve **texto** (árvore UIA da janela, lista de janelas, clipboard, processos) em vez de PNG, cortando tokens do `see_screen`. **Reusa o `win_list` de A.** `see_screen` vira fallback para quando UIA não expõe texto (jogos, canvas, imagem). Absorve o TODO acima.

### 7.C — Arquivos do Windows estruturados — BACKLOG
Fim do "terminal com insert às cegas": (c1) expandir escopo de `edit`/`write` para `/mnt/c/...` com regra de segurança, ou (c2) tool dedicada `win_read`/`win_write`. Contexto: o cérebro (WSL) já alcança `/mnt/c`, mas as tools ficam escopadas na raiz do projeto; fontes do overlay em `C:\Users\<voce>\jarvis-gui` ficam fora. Decidir risco de escrita fora do repo antes de implementar.
