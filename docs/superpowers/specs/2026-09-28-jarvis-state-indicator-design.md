# Jarvis — Indicador visual de estado (overlay/orbe) — Design

- **Data:** 2026-09-28
- **Status:** aprovada (design)
- **Sub-projeto:** 1 de 6 (ver roadmap abaixo)
- **Issues:** #2 (indicador visual)
- **Objetivo:** um sinal visual **discreto, sempre visível e sempre-no-topo** que reflete, em tempo real, o que o Jarvis está fazendo — já que ele roda em segundo plano e o terminal não é opção.

## 1. Visão e roadmap (contexto)

North-star: **assistente de voz sempre ligado** no PC (cérebro no WSL em Python; presença visual no Windows). Capacidades (ver tela, agir no PC) já existem e continuam.

| # | Sub-projeto | Issue | Depende de |
|---|---|---|---|
| 1 | **Emissão de estado + overlay/orbe** (este spec) | #2 | — |
| 2 | Streaming de TTS por sentença | — | — |
| 3 | Wake word ("jarvis") | — | 1 (feedback visual) |
| 4 | Empacotar `.exe` + auto-start no login | #1 | 1, 3 |
| 5 | Personalidade (voz + estilo) | #3 | — |
| 6 | Avatar animado (v3) | #2 | 1 |

Ordem: **1 → (2 em paralelo) → 3 → 4 → 5 → 6**.

## 2. Decisões (brainstorming)

- **Formato:** overlay flutuante (não tray, não avatar nesta fase).
- **Forma:** **orbe** (círculo com glow), sempre-no-topo.
- **Animação:** **expressiva** — gesto próprio por estado (ondas no `listening`, rotação no `transcribing`/`acting`, vibração no `speaking`, flash no `error`).
- **Cor por estado:** `idle` #64748b · `listening` #22d3ee · `transcribing` #a855f7 · `thinking` #34d399 · `speaking` #f59e0b · `acting` #f43f5e · `error` #ef4444.
- **Tecnologia da GUI:** **Tauri** (webview) — cobre o orbe agora e o avatar (v3) depois sem reescrita.
- **Transporte de estado:** **SSE local** (servidor minúsculo em stdlib no processo do loop) — push contínuo, permite, no futuro, reatividade a áudio.
- **Posição/interação:** canto inferior direito, **arrastável**; hover mostra o rótulo; clique abre menu curto (Mudo / Pausar / **Iniciar ou Reiniciar cérebro** / Sair — o rótulo do item de cérebro é dinâmico conforme o estado).
- **Ciclo de vida:** **híbrido** — o overlay sobe o loop (`wsl.exe`) quando necessário e conecta se ele já estiver no ar; auto-start (fase posterior) via atalho na pasta **Startup** do Windows; anti-órfão por keepalive.

## 3. Arquitetura

```
┌─ WSL (cérebro, Python) ─────────────┐        ┌─ Windows (Tauri) ─────────────┐
│ voice/loop.py                       │        │ gui/  overlay (orbe)          │
│   ├─ transições: idle/listening/…   │        │   EventSource /events         │
│   └─ voice/state.py  StateHub       │  SSE   │   orb: cor + animação/estado  │
│        ├─ GET /state   (snapshot)   │ ─────▶ │   canto, top-most, arrastável │
│        ├─ GET /events  (SSE)        │        │   menu no clique              │
│        └─ POST /command (fila) ◀────┼────────┤   POST /command               │
└─────────────────────────────────────┘        │   (inicia loop via wsl.exe)   │
                                               └───────────────────────────────┘
```

## 4. Componentes e interfaces

### `voice/state.py` (novo) — `StateHub`
- `STATES = ("idle","listening","transcribing","thinking","speaking","acting","error")`
- `set(state, detail=None)` — thread-safe; publica o snapshot a todos os assinantes SSE.
- `GET /state` → `{state, detail, ts}` (snapshot atual: usado p/ sincronizar e p/ "cérebro no ar?").
- `GET /events` → SSE: **primeiro o snapshot atual**, depois cada transição; heartbeat a cada ~10s.
- `POST /command` → enfileira `{cmd}`; o loop consome entre etapas.
- Implementação: `ThreadingHTTPServer` + thread daemon, **somente stdlib**.
- UI dev opcional: `GET /` serve um ciclo de estados (usado pela GUI em desenvolvimento).

### `voice/config.py` — novos campos
- `state_port` — env `JARVIS_STATE_PORT`, default `8765`.
- `state_require_gui` — env `JARVIS_REQUIRE_GUI`, default `false`; `true` quando o overlay sobe o loop.

### `voice/loop.py`
- Cria o hub, emite as transições nos pontos certos, consome comandos e encerra limpo.
- Se o hub não subir (ex.: porta ocupada), **avisa e segue sem indicador** — nunca derruba a voz.

### `gui/` (novo, Tauri)
- `EventSource` em `http://localhost:<state_port>/events` → estado → orbe.
- Orbe: cor + animação por estado (ver Seção 5).
- Janela: sem decoração, transparente, always-on-top, canto inferior direito, arrastável.
- Hover: rótulo curto do estado. Clique: menu (Mudo / Pausar / Iniciar|Reiniciar cérebro / Sair).
- Se `/state` não responder: **orbe offline** (cinza, vazado); o item de cérebro vira **Iniciar cérebro**.
- Dev: controle "ciclar estados" para revisar o orbe sem o loop.

## 5. Máquina de estados e pontos de emissão

Por turno: `idle` → `listening` → `transcribing` → `thinking` → `speaking` → `idle`.
- `listening`: durante o record; no modo `auto`, só após o VAD detectar fala (antes disso = `idle`).
- `acting`: modo `--do` / agente `act`.
- Visão: `thinking` (captura + modelo) → `speaking`.
- Falha em qualquer etapa: `error` → `idle`.

| Estado | Cor | Gesto |
|---|---|---|
| idle | #64748b | respira devagar |
| listening | #22d3ee | pulso + ondas (anéis expandindo) |
| transcribing | #a855f7 | rotação |
| thinking | #34d399 | pulso |
| speaking | #f59e0b | vibração (batida) |
| acting | #f43f5e | rotação (engrenagem) |
| error | #ef4444 | flash |

## 6. Comandos (`POST /command`)

Consumidos entre etapas (fila thread-safe):
- `mute` (toggle) — suprime o TTS do próximo turno (segue logando).
- `pause` (toggle) — não capta novos turnos; termina o atual; fica `idle`.
- `quit` — encerra o loop; a GUI passa a mostrar "offline".

## 7. Ciclo de vida (híbrido 1+2)

- O overlay, ao iniciar, consulta `/state`. Se não houver resposta, mostra "offline" e oferece **Iniciar cérebro**, que executa `wsl.exe … python loop.py --voice` (com `JARVIS_REQUIRE_GUI=1`).
- Se o loop já estiver no ar (modo dev/manual), o overlay apenas conecta.
- **Anti-órfão:** com `JARVIS_REQUIRE_GUI=1`, se houver 0 assinantes SSE por ~15s, o loop encerra.
- Auto-start no login (fase posterior, issue #1): atalho do overlay na pasta **Startup** do Windows (não serviço — serviço não acessa microfone/áudio).

## 8. Tratamento de erro

| Situação | Comportamento |
|---|---|
| Porta ocupada / hub não sobe | avisa e roda **sem** indicador; a voz continua |
| GUI ausente | loop segue; com `REQUIRE_GUI=1` e 0 assinantes por ~15s → encerra |
| Cliente SSE morto | descarta só aquele cliente, mantém os demais |
| WSL não alcança o localhost do Windows | URL/host configurável; GUI mostra "offline" |

## 9. Testes

- `StateHub`: snapshot no connect; publicação de transições; heartbeat; fila de comandos; porta ocupada → degradação graciosa.
- `loop`: sequência de estados com hub fake; `acting` no `--do`; `error` + volta a `idle`; caminho anti-órfão.
- `config`: parsing de `JARVIS_STATE_PORT` / `JARVIS_REQUIRE_GUI`.
- `gui`: controle de "ciclar estados" para revisão visual; verificação manual dos gestos por estado.
- Comando de referência: `cd voice && . .venv/bin/activate && pytest -q`.

## 10. Não-objetivos (v1)

- Avatar animado, wake word, orbe reativo ao nível de áudio.
- Painel de configuração / personalidade (#3).
- Empacotamento `.exe` e auto-start no login (#1).
- Histórico de estados.

## 11. Riscos

| Risco | Mitigação |
|---|---|
| Flakiness do localhost no WSL2 | URL/host configurável; estado "offline" claro |
| Setup do Tauri no Windows (Rust/WebView2) | one-time; documentar |
| Thread daemon em CLI + shutdown | `stop()` explícito; coberto por teste |
| Indicador atrapalhar a voz | falha do hub vira aviso; nunca exceção fatal |

## 12. Critério de sucesso

O orbe reflete cada estado em **<200ms** durante o uso por voz; o menu ("Mudo/Pausar/Reiniciar/Sair") e o "Iniciar cérebro" funcionam; o indicador **nunca** derruba a voz; com `JARVIS_REQUIRE_GUI=1`, fechar o overlay encerra o loop.
