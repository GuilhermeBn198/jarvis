# Fase C2+C3 — Verificação (voz: TTS SAPI + STT/captura)

Data: 2026-09-27
Branch: `feat/fasec23-voice`

## Unit
- [x] `pytest -q` = **35 passed** (0 fail, 0.08s)

  Comando:

      cd voice && . .venv/bin/activate && pytest -q

## Smoke (real)
- [x] `python loop.py --voice --once 1` completa sem crash (exit 0).

  Comando:

      cd voice && timeout 120 python loop.py --voice --once 1 ; echo "exit=$?"

  Saída real:

      [voz] nada transcrito
      exit=0

  (Neste ambiente não há fala no mic; a captura/STT rodam e devolvem vazio — o loop
  informa e encerra a rodada sem travar.)

## Correções da revisão final (C2+C3)
- **F1** `loop.py`: quando `speak` levanta `VoiceError`, a resposta **não é mais
  descartada** — é impressa em texto (`[fallback texto] <resposta>`), conforme spec §6
  ("SAPI indisponível → cai para texto").
- **F2** `capture.py`: `subprocess.run(..., errors="replace")`, espelhando o `tts.py`;
  `UnicodeDecodeError` (um `ValueError`, não `OSError`) não escapa mais.
- **F3** `loop.py`: contador de `VoiceError` consecutivos (default 3) aborta o loop com
  mensagem clara ("N falhas seguidas ... abortando"), evitando spin a plena velocidade
  com binário/mic ausente; zera em iteração bem-sucedida.
- **F6** `loop.py`/`capture.py`: aviso `[voz] nada transcrito` em transcrição vazia;
  `FFMPEG_EXE` nomeado na mensagem de erro do `record`; `--once` exige N >= 1 (rejeita 0
  com exit 2).
- **F6** spec §2/§3/§5 atualizadas de `whisper.cpp`/`WHISPER_BIN` para
  `faster-whisper`/`WHISPER_MODEL`.

## Deferral deliberado: `serve` (spec §4)
A spec §4 previa que o client de produção do C3 fosse o **`opencode serve`** (servidor
HTTP longo, para não pagar ~60–90 s de startup por turno). **Isso foi deliberadamente
adiado.** A medição real do `RunClient` (um `opencode run --pure` por turno) deu
**~13 s**, bem abaixo da estimativa conservadora, o que é aceitável para uso local.
Mantemos o `RunClient`; a migração para `opencode serve` fica como trabalho futuro.
Referência: `docs/superpowers/specs/2026-09-26-jarvis-fasec-voice-design.md` §4.
