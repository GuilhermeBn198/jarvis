# Jarvis Fase C — Voz (STT/TTS) Design

- **Data:** 2026-09-26
- **Status:** proposta (revisão)
- **Fase:** C. Depende de A/B (em `main`). Sem mudanças no opencode.
- **Objetivo:** falar com o agente por voz e ouvir a resposta — `mic → STT → opencode → resposta → TTS`, local-first.

---

## 1. Contexto e viabilidade (validada)

O WSL **não tem áudio** (`/dev/snd` só `timer`); o mic/alto-falantes vivem no Windows. Validações feitas nesta máquina:

| Item | Resultado |
|---|---|
| TTS via **SAPI** (PowerShell) | ✅ funciona, **zero install** (WAV de 158 KB gerado) |
| **whisper.cpp** | ✅ binários: **Ubuntu x64** (WSL) e Windows CPU/BLAS. ❌ sem binário **Vulkan/Windows** (GPU exigiria build; sem cmake/MSVC) |
| Captura de áudio | ⚠️ **sem ffmpeg/sox** → instalar **ffmpeg** (winget); mic **"Microphone (FIFINE Microphone)"** presente |
| `wsl.exe … opencode` | ⚠️ falha (PATH não-interativo) → caminho absoluto `~/.opencode/bin/opencode` |
| `opencode run` (cold) | ⚠️ **~60–90 s** de startup por execução → inviável por turno; usar **`opencode serve`** (servidor longo) |

**Decisão de arquitetura:** a ponte roda **no WSL** (onde vive o opencode) e alcança o áudio do Windows por **subprocess** (`powershell.exe`, `ffmpeg.exe`). Isso elimina Python-no-Windows, libs de áudio no Node, o problema de PATH e a ausência de binário Vulkan.

## 2. Arquitetura

```
[mic] ──ffmpeg.exe(dshow)──▶ wav
   │(WSL chama o ffmpeg.exe do Windows)
   ▼
STT: whisper.cpp (binário Linux, CPU)  → texto
   │
   ▼
AgentClient: opencode serve (HTTP/SDK)  → resposta   (fallback: `opencode run`)
   │
   ▼
TTS: powershell.exe SAPI  → alto-falante
```

## 3. Componentes e interfaces (WSL, Python)

```
voice/
  config.py          # caminhos e env (OPENCODE_BIN, WHISPER_BIN, WHISPER_MODEL, FFMPEG_EXE, MIC_DEVICE)
  agent_client.py    # AgentClient.ask(task) -> str  (ServeClient; RunClient como fallback simples)
  tts.py             # speak(text, to_file=None) via powershell SAPI
  stt.py             # transcribe(wav_path) -> str  via whisper.cpp
  capture.py         # record(seconds) -> wav_path  via ffmpeg.exe (dshow)
  loop.py            # o ciclo: grava → transcreve → pergunta → fala
  tests/
```

**Contratos (puros, testáveis com subprocess fake):**
- `agent_client.ask(task: str, timeout_s: int = 300) -> str`
- `tts.speak(text: str, to_file: str | None = None) -> None`
- `stt.transcribe(wav_path: str) -> str` (retorna `""` se vazio)
- `capture.record(seconds: float) -> str` (caminho do WAV)

Cada módulo isola **um** subprocess/efeito; o `loop.py` só orquestra.

## 4. Estágios (cada um provado isolado)

- **C1 — Ponte de texto (sem áudio):** `stdin → agent_client.ask → stdout`. Valida a integração com o agente. **Risco ~zero.**
- **C2 — TTS:** resposta falada via SAPI (`speak`). Já validado; entra o wrapper.
- **C3 — STT + captura:** `ffmpeg.exe` grava N s (push-to-talk simples = Enter para iniciar/parar), `whisper.cpp` transcreve, alimenta C1, e a resposta é falada (C2). Fecha o loop.
- **C4 (opcional) — hotword:** wake-word ("jarvis"). Adiado.

**Latência:** a partir do C3, o `AgentClient` de produção é o **`serve`** (servidor `opencode serve` já no ar), não o `run` — senão cada turno pagaria ~60–90 s.

## 5. Configuração

- `OPENCODE_BIN` (default `~/.opencode/bin/opencode`), `OPENCODE_SERVER_URL` (default `http://127.0.0.1:4096`).
- `WHISPER_BIN` (binário Linux do whisper.cpp), `WHISPER_MODEL` (ex.: `ggml-base.bin`), `FFMPEG_EXE` (caminho do `ffmpeg.exe` no Windows), `MIC_DEVICE` (nome dshow).

## 6. Tratamento de erro

| Situação | Comportamento |
|---|---|
| binário ausente (whisper/ffmpeg/opencode) | erro claro nomeando a env/instalação |
| silêncio/transcrição vazia | não chama o agente; informa |
| agente sem resposta / timeout | erro claro; segue o loop |
| SAPI indisponível | cai para texto (imprime a resposta) |

## 7. Testes

- **Unit:** cada módulo com subprocess fake (monkeypatch), verificando os **argumentos** montados (ex.: a linha do `ffmpeg` com `-f dshow -i audio="<MIC>"`, a chamada SAPI, o comando do whisper).
- **Integração (manual, real):** C2 gera WAV válido; C3 transcreve um WAV de teste (ex.: o próprio WAV do SAPI) e fecha o loop.

## 8. Não-objetivos

- Hotword, streaming contínuo, conversa multi-turno contínua (C4+).
- Whisper na GPU (sem binário Vulkan; exigiria build).
- Mudanças no opencode/agentes (A/B já entregaram).

## 9. Riscos

| Risco | Mitigação |
|---|---|
| Instalar **ffmpeg** no Windows | `winget install ffmpeg`; nome do device via `ffmpeg -list_devices true -f dshow -i dummy` |
| Modelo whisper (~150 MB) | download único (`ggml-base.bin`) |
| Latência do agente | usar `opencode serve` (não `run` por turno) |
| Qualidade STT CPU | modelo `base`/`small`; GPU depois (build) |

## 10. Critério de sucesso

Falar uma frase → ver o texto transcrito → receber a resposta **falada**, num loop local, com cada salto (captura, STT, agente, TTS) verificável isoladamente.
