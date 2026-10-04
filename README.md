# jarvis

Assistente pessoal por voz, **sempre ligado**, que roda no seu PC: o "cérebro" vive no **WSL (Python)** e conversa com o **Windows** para ouvir o microfone, falar, ver a tela e executar ações. Há uma presença visual discreta no Windows — um **orbe** que mostra o que o Jarvis está fazendo.

> Estado atual: funcional e em evolução. Veja **Limitações** e **Aprimoramentos planejados**.

---

## Índice

- [O que é](#o-que-é)
- [Capacidades](#capacidades)
- [Arquitetura](#arquitetura)
- [Requisitos](#requisitos)
- [Instalação](#instalação)
- [Como usar](#como-usar)
- [Configuração (variáveis de ambiente)](#configuração-variáveis-de-ambiente)
- [Limitações conhecidas](#limitações-conhecidas)
- [Aprimoramentos planejados](#aprimoramentos-planejados)
- [Estrutura do repositório](#estrutura-do-repositório)
- [Testes](#testes)
- [Documentação](#documentação)
- [Licença](#licença)

---

## O que é

O Jarvis é um loop de voz local: **microfone → transcrição (STT) → agente (LLM) → fala (TTS)**, com modos especiais para **ver a tela** e **agir no PC**. O agente é o [`opencode`](https://opencode.ai) (via `serve`): a conversa usa o agente `chat`, que tem as tools `see_screen` e `act_*`, e o loop orquestra captura, STT, agente e TTS.

Divisão de responsabilidades:

- **WSL (Linux/Python)** — toda a lógica: captura de áudio, STT, agente, TTS, visão, ações e o servidor de estado.
- **Windows** — binários de áudio/voz (`ffmpeg.exe`, `piper.exe`, `ffplay.exe`), `powershell.exe` (SAPI e ações) e o **overlay visual** (Tauri).

---

## Capacidades

- **Conversa por voz** com gravação automática por detecção de fala (VAD/`silencedetect`), push-to-talk ou janela fixa.
- **STT** com `faster-whisper` (VAD anti-alucinação) e **TTS** com `piper` (rápido) ou SAPI (fallback sem dependências).
- **Streaming de TTS por sentença** — começa a falar enquanto o texto ainda é gerado, com fallback para o caminho bloqueante (ver limitações sobre o ganho).
- **Visão de tela** (`--see` ou a palavra-gatilho "olha"): captura a tela e pergunta a um modelo de visão. O conteúdo da tela é tratado como **não-confiável** (o agente de visão não tem ferramentas).
- **Ações no PC** (`--do` ou o agente `act`): digitar, teclas, clicar e abrir coisas no Windows, via as tools `act_*`, protegidas por um **SafetyGate** (regras de segurança).
- **Ações em segundo plano (opt-in):** `act_type`/`act_key` aceitam `window`/`hwnd` (ou `mode="background"`) para agir sem roubar foco/cursor via UI Automation + PostMessage; `mode="foreground"` explícito força o caminho em foco mesmo com `window`/`hwnd`. `win_list` lista as janelas. Na injeção de **texto**, apps que ignoram entrada em background retornam `unconfirmed` e o Jarvis pede confirmação antes de trazer a janela para frente; já `act_key` apenas reporta `verificacao indisponivel` e **não** pede consentimento. O `act_type` via UIA `ValuePattern` **define** o valor do campo (substitui o conteúdo existente), não insere no cursor; o fallback `WM_CHAR` é best-effort (postado à janela-alvo e alguns apps o ignoram). Clicar em controles em background ainda nao e suportado. Verificação de injeção em background E2E ainda pendente (manual).
- **Indicador visual de estado** (overlay Tauri): um **orbe** sempre-no-topo, com cor e animação por estado — `idle`, `listening`, `transcribing`, `thinking`, `speaking`, `acting`, `error`. Clicável (menu: Mudo / Pausar / Iniciar|Reiniciar cérebro / Sair) e arrastável.
- **Comandos pelo overlay**: `mute` (silencia), `pause` (não capta novos turnos) e `quit` (encerra o loop), além de subir o cérebro no WSL.
- **Bridge de texto** (stdin → agente → stdout), útil para scripts e testes.
- **Vários agentes** (`opencode.json`): `chat` (conversa rápida; tem `see_screen` e `act_*`), `act` (ações), `orchestrator` (tarefas pesadas) e `local-executor` (sub-tarefas baratas no modelo local via Ollama).
- **Delegação ao modelo local** (GPU) via MCP `delegate_local` (opcional).

---

## Arquitetura

```
┌─ WSL (cérebro, Python) ─────────────┐        ┌─ Windows ─────────────────────┐
│ voice/loop.py                       │        │  ffmpeg.exe / piper.exe /      │
│   ├─ capture (ffmpeg dshow) ────────┼───────▶│  ffplay.exe / powershell.exe   │
│   ├─ stt (faster-whisper)           │        │                                │
│   ├─ agent_client (opencode serve) ─┼─SSE────┼─▶ overlay Tauri (orbe)         │
│   ├─ tts (piper / sapi)             │        │                                │
│   ├─ vision (captura + modelo)      │        │                                │
│   └─ state.py StateHub (SSE/HTTP) ──┼────────┼─▶ POST /command (menu)         │
└─────────────────────────────────────┘        └────────────────────────────────┘
```

- O agente (`chat`) conversa via `opencode serve` (HTTP/SSE); o loop sobe o servidor automaticamente se preciso.
- O `StateHub` (`voice/state.py`) expõe `GET /state`, `GET /events` (SSE) e `POST /command` em `127.0.0.1:8765`; o overlay assina o SSE.
- Se o `serve` não estiver disponível, o loop cai para o backend `run` (mais lento) — a voz continua funcionando.

---

## Requisitos

**Base (WSL/Linux):**
- **WSL2** (Ubuntu 22.04+) com interop para executar `.exe` do Windows.
- **Python 3.10** no WSL.
- **`opencode`** CLI instalado e autenticado (`~/.opencode/bin/opencode` por padrão).
- **`faster-whisper`** (instalado via `requirements.txt`; baixa o modelo na 1ª transcrição).

**Windows (caminhos default em `voice/config.py`, sobrescrevíveis por env):**
- **`ffmpeg.exe`** — captura do microfone (`dshow`). Default no código: `/mnt/c/Users/<seu-usuario>/tools/ffmpeg/.../ffmpeg.exe` (ajuste por `FFMPEG_EXE`).
- **`piper.exe`** + voz `.onnx` — TTS. Default no código: `/mnt/c/Users/<seu-usuario>/tools/piper/...` (ajuste por `PIPER_EXE`/`PIPER_MODEL`).
- **`ffplay.exe`** — reprodução do WAV do piper.
- **`powershell.exe`** — TTS SAPI e ações no PC (já vem no Windows).

**Overlay visual (opcional, Windows):**
- **Rust** (toolchain `stable`, host `x86_64-pc-windows-msvc`).
- **Microsoft C++ Build Tools** (workload "Desktop development with C++").
- **WebView2 Runtime** (já incluso no Windows 10/11).

---

## Instalação

### 1. Base no WSL

```bash
git clone https://github.com/GuilhermeBn198/jarvis.git jarvis
cd jarvis/voice
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt      # faster-whisper (+ pytest em dev)
```

Confirme o `opencode`:

```bash
opencode --version          # ou defina OPENCODE_BIN
opencode serve --port 4096 &   # opcional: o loop sobe sozinho se precisar
```

### 2. Binários no Windows (áudio/voz)

Baixe e aponte (ou ajuste os env se os seus caminhos diferirem):

- **ffmpeg/ffplay** — build Windows; exemplo de caminho em `FFMPEG_EXE` / `FFPLAY_EXE`.
- **piper** — binário + voz (`pt_BR-faber-medium.onnx` ou outra); `PIPER_EXE` / `PIPER_MODEL`.
- Descubra o nome do microfone:

```bash
ffmpeg.exe -list_devices true -f dshow -i dummy
# ajuste MIC_DEVICE se necessário
```

> Alternativa sem dependências: `AGENT_BACKEND=run` e `TTS_BACKEND=sapi` (mais lento, mas não exige piper/ffplay).

### 3. Overlay visual (Windows, opcional)

Pré-requisitos: Rust + MSVC Build Tools + WebView2 (veja **Requisitos**).

```powershell
cd gui\src-tauri
cargo run            # abre o orbe (fundo transparente, sempre-no-topo)
```

> O build do app embuta o frontend (`gui/src`) no binário; não precisa de Node.

---

## Como usar

### Loop de voz

```bash
./jarvis --voice            # loop contínuo (Ctrl+C para sair)
./jarvis --voice --once 1   # um turno (teste)
```

O launcher `./jarvis` ativa o venv de `voice/` sozinho (não precisa de `source .venv/bin/activate`). Equivalente manual:

```bash
cd voice && . .venv/bin/activate && python loop.py --voice
```

**Calibrar o microfone** (se ele dispara com ruído ou não ouve você):
```bash
./jarvis --list-mics      # lista os microfones (dshow) e marca o ativo (*)
./jarvis --mic-level      # mede o ruído de fundo (~5s) e sugere VOICE_NOISE_DB
```
Em silêncio, veja o `media` (dB) e use `VOICE_NOISE_DB` ≈ media + 8 (mais negativo = mais sensível). **Se `media` vier perto de −90 dB, o mic está mudo/sem ganho** — troque de device (abaixo) ou ajuste o volume/mute no Windows.

No **overlay** (menu → **Configurações**) você escolhe o **Microfone ativo** (lista os devices), usa *Medir microfone* e salva. Os ajustes ficam em `~/.config/jarvis/settings.json` (o env tem precedência) e valem ao **reiniciar o cérebro**.

**Modos de entrada** (`VOICE_INPUT`):
- `auto` (default) — grava quando você **fala** (VAD), para após ~1s de silêncio.
- `ptt` — push-to-talk (Enter inicia / Enter para).
- `fixed` — janela fixa de `RECORD_SECONDS` segundos.

### Ver a tela

```bash
./jarvis --see "o que está na tela?"      # fala + mostra (gatilho de voz: "olha, ...")
./jarvis --see-text "o que está na tela?" # só imprime a descrição (usado pela tool see_screen)
```

Na voz, **linguagem natural**: o agente `chat` tem a tool **`see_screen`** — basta pedir ("dá uma olhada na minha tela") que o modelo decide chamá-la. O conteúdo da tela vai para o agente **`vision`** (sem ferramentas) — nunca executa tools.

### Agir no PC

```bash
./jarvis --do "abra o navegador e pesquise por X"    # agente act, caminho bloqueante
```

Na voz, **linguagem natural**: o agente `chat` agora tem as tools **`act_type`/`act_key`/`act_open`/`act_click`** — basta pedir ("abre o navegador") que o modelo decide. Tudo passa pelo **SafetyGate** (`ask`/`deny` viram bloqueio para `act_*`).

### Bridge de texto

```bash
echo "responda apenas: ok" | ./jarvis
```

### Overlay

Com o cérebro no ar (`:8765`), rode o overlay no Windows (`cargo run` em `gui/src-tauri`, ou o exe em `C:\caminho\para\jarvis-overlay.exe`). O orbe reflete o estado em tempo real; o menu permite mutar, pausar, iniciar/reiniciar o cérebro e sair. Ao abrir, se o cérebro estiver offline, o overlay **sobe o loop sozinho**. **Sair** encerra o cérebro no WSL (o overlay mata o processo; se escapar, `pkill -f loop.py` no WSL).

O menu **Configurações** abre um painel para escolher o **Microfone ativo**, calibrar (*Medir microfone*), ajustar sensibilidade/tempos de captura, **modo de entrada** (`auto`/`ptt`/`fixed`), **voz** (`piper`/`sapi`) e ligar/desligar o streaming de TTS.

**Diagnóstico:** o overlay redireciona stdout/stderr do cérebro para `%LOCALAPPDATA%\jarvis\brain.log` — é lá que aparecem `[voz] nada transcrito`, `[erro] ...` etc.

**Sempre ligado:** crie um atalho do exe na pasta **Startup** do Windows (`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`) para abrir no login.

**Configuração do overlay:** o arquivo `jarvis-config.json` **ao lado do exe** pode sobrescrever o comando do cérebro e a distro do WSL:

```json
{
  "loop_cmd": "JARVIS_REQUIRE_GUI=1 /home/<seu-usuario>/github/jarvis/jarvis --voice",
  "distro": null
}
```
(veja `gui/jarvis-config.example.json`). `JARVIS_LOOP_CMD` também pode fixar o comando no build do Rust.


> Para o modo "sempre ligado" com anti-órfão, suba o loop com `JARVIS_REQUIRE_GUI=1` (o overlay já faz isso ao "Iniciar cérebro"): se o overlay sumir, o loop encerra em ~15s.

---

## Configuração (variáveis de ambiente)

Todas são opcionais (defaults em `voice/config.py`). As principais:

| Variável | Default | Descrição |
|---|---|---|
| `AGENT_BACKEND` | `serve` | backend do agente (`serve` rápido, `run` fallback) |
| `OPENCODE_SERVER_URL` | `http://127.0.0.1:4096` | URL/base do `opencode serve` |
| `OPENCODE_BIN` | `~/.opencode/bin/opencode` | binário do agente |
| `JARVIS_PROJECT_ROOT` | raiz do repo (auto) | cwd do `opencode` (precisa ser a raiz p/ carregar `.opencode/plugins`: `act_*`, `see_screen`, SafetyGate) |
| `VOICE_AGENT` | `chat` | agente do opencode para a conversa |
| `VOICE_TIMEOUT_S` | `300` | timeout do agente por turno |
| `VOICE_INPUT` | `auto` | modo de entrada (`auto`/`ptt`/`fixed`) |
| `RECORD_SECONDS` | `5` | duração da janela (`fixed`) |
| `VOICE_LANGUAGE` | `pt` | idioma do STT |
| `WHISPER_MODEL` | `base` | modelo do `faster-whisper` |
| `TTS_BACKEND` | `piper` | TTS (`piper`/`sapi`) |
| `PIPER_EXE`, `PIPER_MODEL`, `FFPLAY_EXE`, `PIPER_OUT_WAV` | caminhos Windows | TTS piper |
| `FFMPEG_EXE`, `MIC_DEVICE` | caminho Windows / device | captura de áudio (o `MIC_DEVICE` também vem de `settings.json`) |
| `VOICE_NOISE_DB` | `-35` | limiar (dB) do `silencedetect`: abaixo disso é silêncio. **Menos negativo = menos sensível** (ideal: ~6–10 dB acima do ruído de fundo) |
| `VOICE_SILENCE_S` | `1.0` | silêncio (s) necessário para encerrar a fala |
| `VOICE_WAIT_S` | `8.0` | espera máxima pela 1ª fala (sem fala, desiste) |
| `VOICE_MAX_S` | `15.0` | teto absoluto da gravação por turno |
| `VOICE_MIN_SPEECH_S` | `0.4` | duração mínima (s) de um trecho não-silencioso para valer como fala (rejeita ruído curto) |
| `JARVIS_VOICE_LOCK` | `/tmp/jarvis-voice.lock` | trava de instância única do `--voice` |
| `JARVIS_HEARTBEAT` | `false` | loga `[hb]` por estágio + `[watchdog]` se o loop travar (vai pro `brain.log`) |
| `VISION_MODEL` | `opencode-go/deepseek-v4-flash-vision-exp` | modelo de visão |
| `VISION_TRIGGER` | `olha` | palavra que dispara a visão na voz |
| `VOICE_STREAM_TTS` | `true` | streaming de TTS por sentença |
| `VOICE_STREAM_IDLE_MS` | `400` | pausa que dispara o flush do pedaço |
| `VOICE_STREAM_MIN_CHARS` | `15` | mínimo de caracteres por pedaço |
| `JARVIS_STATE_PORT` | `8765` | porta do `StateHub` (SSE/HTTP) |
| `JARVIS_REQUIRE_GUI` | `false` | anti-órfão: encerra o loop se o overlay sumir |
| `VOICE_LOG` | `~/.local/share/jarvis/voice-log.jsonl` | log dos turnos (JSONL) |

Detalhes e a lista completa: `voice/README.md`.

---

## Limitações conhecidas

- **Latência**: um turno conversacional via `serve`+`piper` fica na casa de poucos segundos. O **streaming de TTS** foi implementado, mas o ganho medido foi **modesto** (~7–20%) porque o tempo até o primeiro token domina e o modelo/API costuma entregar a resposta em poucos blocos grandes. `first_audio_s`/`stream` ficam no `convlog` para acompanhar.
- **Caminhos do Windows hardcoded** nos defaults (`ffmpeg`, `piper`, `shot.png`, etc.) — precisam ser ajustados por env em outra máquina.
- **Microfone "preso"** (issue [#4](https://github.com/GuilhermeBn198/jarvis/issues/4)): a captura `dshow` pode segurar o dispositivo, deixando o mic indisponível para outros apps (ex.: Discord). Mitigado por: não rodar headless sem overlay (`JARVIS_REQUIRE_GUI`), trava de instância única (`JARVIS_VOICE_LOCK`) e limpeza do `ffmpeg`. **Se o mic sumir em outros apps:** em *Configurações de Som → Microfone → Propriedades → Avançado*, **desmarque** "Permitir que os aplicativos tenham controle exclusivo" e, se preciso, reinicie o dispositivo/PC.
- **Sem wake word**: hoje a entrada é VAD/PTT — ruído pode disparar.
- **Sem barge-in**: não dá para interromper a fala do Jarvis falando por cima.
- **Streaming só na conversa**: visão (`--see`) e ações (`--do`) usam o caminho bloqueante.
- **Dependência do `serve`**: `opencode serve`/modelo são externos; sem eles, cai para `run` (lento) ou falha.
- **Visão e ações** são v1: tela inteira, sem região/janela ativa; ações dependem do SafetyGate e das regras de segurança.
- **Overlay é Windows-only** (Tauri) e exige Rust/MSVC/WebView2.

---

## Aprimoramentos planejados

Roadmap "sempre ligado" (issues no GitHub):

| # | Item | Issue |
|---|---|---|
| 1 | **Wake word** ("jarvis, ...") para acordar sem falso positivo | — |
| 2 | **Empacotar `.exe`** e auto-start no login (sem invocar Python) | [#1](https://github.com/GuilhermeBn198/jarvis/issues/1) |
| 3 | **Personalidade configurável** — tonalidade de voz e estilo de resposta | [#3](https://github.com/GuilhermeBn198/jarvis/issues/3) |
| 4 | **Avatar animado** (v3 do indicador, sobre o orbe) | [#2](https://github.com/GuilhermeBn198/jarvis/issues/2) |
| 5 | **Orbe reativo ao áudio** (v2 do indicador) | [#2](https://github.com/GuilhermeBn198/jarvis/issues/2) |
| 6 | **Corrigir o mic preso** (anti-órfão + limpeza do `ffmpeg` + modo compartilhado) | [#4](https://github.com/GuilhermeBn198/jarvis/issues/4) |
| 7 | Roteamento determinístico nuvem↔local (proxy/LiteLLM) | — |
| 8 | Classificador aprendido para roteamento | — |

Backlog detalhado: `docs/backlog.md`.

---

## Estrutura do repositório

```
jarvis/
├── jarvis                 # launcher do cérebro (WSL): ativa o venv e roda o loop
├── voice/                 # cérebro (Python, roda no WSL)
│   ├── loop.py            # loop de voz, --see, --do, bridge de texto
│   ├── agent_client.py    # RunClient / ServeClient (+ streaming SSE)
│   ├── capture.py         # gravação via ffmpeg dshow (auto/ptt/fixed)
│   ├── stt.py             # faster-whisper
│   ├── tts.py             # piper / sapi
│   ├── stream.py          # SentenceChunker + Speaker (streaming de TTS)
│   ├── state.py           # StateHub (SSE/HTTP/comandos)
│   ├── vision.py          # captura + visão
│   ├── serve.py           # garante o opencode serve
│   ├── config.py          # config por env
│   └── tests/             # pytest (~224 testes)
├── gui/                   # overlay (Tauri 2, Rust + frontend estático)
│   └── src-tauri/         # app Rust (orbe + start_brain)
├── .opencode/             # agentes, plugins (SafetyGate) e tools act_*
├── mcp_servers/
│   └── delegate_local/    # MCP de delegação ao modelo local (Ollama)
├── docs/
│   ├── backlog.md
│   └── superpowers/       # specs e planos de cada fase
└── opencode.json          # agentes e MCP
```

---

## Testes

```bash
cd voice
. .venv/bin/activate
pytest -q
```

---

## Documentação

- **Backlog**: `docs/backlog.md`
- **Specs/design**: `docs/superpowers/specs/`
- **Planos de implementação**: `docs/superpowers/plans/`
- **Voz (detalhes de env, modos e dependências)**: `voice/README.md`

Histórico de fases: inferência/roteamento (Fase 1), delegação local (2a), SafetyGate (2b), ponte de texto (C1), voz TTS/STT (C2/C3), visão de tela (D), ações no PC (E), indicador de estado e streaming de TTS.

---

## Licença

Distribuído sob a **Apache License 2.0** — veja [`LICENSE`](LICENSE).
