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

Por padrão a voz usa `serve` (agente) + `piper` (TTS). O loop sobe o
`opencode serve` automaticamente se ele ainda não estiver no ar; se não
conseguir, avisa e cai para o backend `run` (mais lento), então a voz
continua funcionando.

## Pré-requisitos e configuração

### Agente (`serve`, default)
O loop chama `GET {OPENCODE_SERVER_URL}/global/health` e, se não houver
servidor saudável, executa
`opencode serve --port <porta>` em segundo plano (log em
`/tmp/opencode/serve.log`, sobrescreva com `SERVE_LOG`). Para subir manualmente:

    opencode serve --port 4096 &

`OPENCODE_SERVER_URL` (default `http://127.0.0.1:4096`) é a fonte de verdade:
a porta usada na subida é derivada dele.

### TTS (`piper`, default)
O `piper` precisa de:
- `PIPER_EXE` e `PIPER_MODEL` apontando para o binário e a voz `.onnx`
  baixados (defaults em `config.py`);
- `ffplay.exe` para reproduzir o WAV (`FFPLAY_EXE`).

Para dispensar essas dependências, use os fallbacks de zero dependência:
`AGENT_BACKEND=run` e/ou `TTS_BACKEND=sapi`.

### Por que esses defaults
Medido neste ambiente: `serve` ~4s/turno contra `run` ~16s; `piper` ~1,1s
contra `sapi` ~4s. No total, `serve`+`piper` ~4,8s contra `run`+`sapi` ~20s.

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
| `AGENT_BACKEND` | `serve` | backend do agente (`serve` rápido, `run` fallback) |
| `OPENCODE_SERVER_URL` | `http://127.0.0.1:4096` | URL/base do `opencode serve` |
| `SERVE_LOG` | `/tmp/opencode/serve.log` | log do `opencode serve` iniciado pelo loop |
| `TTS_BACKEND` | `piper` | TTS (`piper` rápido, `sapi` fallback) |
| `PIPER_EXE` | caminho do `piper.exe` (acima) | binário do piper |
| `PIPER_MODEL` | voz `pt_BR-faber-medium.onnx` (acima) | modelo de voz do piper |
| `FFPLAY_EXE` | caminho do `ffplay.exe` (acima) | reprodução do WAV do piper |
| `PIPER_OUT_WAV` | `C:\Users\bguil\tools\piper\out.wav` | WAV temporário do piper |
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
