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

## 1.1 Pivot do STT (validação em ambiente)

O binário `whisper.cpp` (Linux) falhou por depender de `libgomp.so.1`, ausente no WSL (exigiria `apt`/sudo). **Pivotamos o STT para `faster-whisper` (pip, CPU)** — sem libs de sistema, validado: transcreveu um WAV gerado pelo SAPI em português. O `ffmpeg` permanece **apenas para a captura** (dshow/Windows).

## 2. Arquitetura

```
[mic] ──ffmpeg.exe(dshow)──▶ wav
   │(WSL chama o ffmpeg.exe do Windows)
   ▼
STT: faster-whisper (pip, CPU)  → texto
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
  config.py          # caminhos e env (OPENCODE_BIN, WHISPER_MODEL, FFMPEG_EXE, MIC_DEVICE, POWERSHELL_EXE)
  agent_client.py    # AgentClient.ask(task) -> str  (ServeClient; RunClient como fallback simples)
  tts.py             # speak(text, to_file=None) via powershell SAPI
  stt.py             # transcribe(wav_path) -> str  via faster-whisper
  capture.py         # record(seconds) -> wav_path  via ffmpeg.exe (dshow)
  loop.py            # o ciclo: grava → transcreve → pergunta → fala
  tests/
```

**Contratos (puros, testáveis com subprocess fake):**
- `agent_client.ask(task: str, timeout_s: int = 300) -> str`
  - Nota (C1): o contrato efetivo do C1 é o método `RunClient.ask(task, timeout_s=None)`;
    isso supersede a redação "ask module-level" desta seção.
- `tts.speak(text: str, to_file: str | None = None) -> None`
- `stt.transcribe(wav_path: str) -> str` (retorna `""` se vazio)
- `capture.record(seconds: float) -> str` (caminho do WAV)

Cada módulo isola **um** subprocess/efeito; o `loop.py` só orquestra.

## 4. Estágios (cada um provado isolado)

- **C1 — Ponte de texto (sem áudio):** `stdin → agent_client.ask → stdout`. Valida a integração com o agente. **Risco ~zero.**
- **C2 — TTS:** resposta falada via SAPI (`speak`). Já validado; entra o wrapper.
- **C3 — STT + captura:** `ffmpeg.exe` grava N s (push-to-talk simples = Enter para iniciar/parar), `whisper.cpp` transcreve, alimenta C1, e a resposta é falada (C2). Fecha o loop.
- **C4 (opcional) — hotword:** wake-word ("jarvis"). Adiado.

**Latência:** a partir do C3, o `AgentClient` de produção era previsto como o **`serve`** (servidor `opencode serve` já no ar), não o `run` — senão cada turno pagaria ~60–90 s.

> **Deferral (C2+C3, 2026-09-27):** o `ServeClient` **não** foi implementado nesta fase. A medição real de `RunClient.ask` (um `opencode run --pure` por turno) deu **~13 s**, não os ~60–90 s estimados no cold start, o que é aceitável para uso local. Mantém-se o `RunClient` como client de produção do C3; migrar para `opencode serve` fica registrado como trabalho futuro (ver `docs/notes/fasec-verification.md`).

## 5. Configuração

- `OPENCODE_BIN` (default `~/.opencode/bin/opencode`), `OPENCODE_SERVER_URL` (default `http://127.0.0.1:4096`).
- `WHISPER_MODEL` (modelo do faster-whisper, ex.: `base`), `FFMPEG_EXE` (caminho do `ffmpeg.exe` no Windows), `MIC_DEVICE` (nome dshow).

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
