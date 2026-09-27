# voice (jarvis Fase C)

Ponte de texto: stdin → agente (opencode) → stdout.

## Rodar
    cd voice
    . .venv/bin/activate
    echo "responda apenas: ok" | python loop.py

### Loop de voz (microfone → STT → agente → TTS)
    . .venv/bin/activate
    python loop.py --voice          # loop de voz (Ctrl+C para sair)
    python loop.py --voice --once 1 # uma rodada (para teste)

## Pré-requisitos e configuração

### Python
    cd voice
    python -m venv .venv
    . .venv/bin/activate
    pip install -r requirements.txt   # faster-whisper (STT, CPU)

### Windows
- **ffmpeg** é obrigatório para a captura (dshow). O default aponta para
  `/mnt/c/Users/bguil/tools/ffmpeg/ffmpeg-master-latest-win64-gpl/bin/ffmpeg.exe`;
  sobrescreva com `FFMPEG_EXE` se o seu caminho for outro.
- O **microfone** é acessado pelo ffmpeg do Windows; confira o nome do device com
  `ffmpeg -list_devices true -f dshow -i dummy`.

### Primeira execução
- O `faster-whisper` baixa o modelo na primeira transcrição (~150 MB para o `base`).

### Variáveis de ambiente
| Variável | Default | Descrição |
|---|---|---|
| `FFMPEG_EXE` | caminho do ffmpeg.exe do Windows (acima) | binário de captura |
| `MIC_DEVICE` | `Microphone (FIFINE Microphone)` | nome do device dshow |
| `WHISPER_MODEL` | `base` | modelo do faster-whisper |
| `RECORD_SECONDS` | `5` | duração da gravação por turno |
| `VOICE_LANGUAGE` | `pt` | idioma do STT |
| `POWERSHELL_EXE` | `powershell.exe` | PowerShell para o TTS (SAPI) |
| `OPENCODE_BIN` | `~/.opencode/bin/opencode` | binário do agente |
| `VOICE_TIMEOUT_S` | `300` | timeout do agente por turno |

## Testes
    . .venv/bin/activate && pytest -q
