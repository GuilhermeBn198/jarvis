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

#### Gravação automática por fala (default)
Por padrão a gravação é **automática** (`VOICE_INPUT=auto`): sem apertar tecla,
o `ffmpeg` do Windows roda `silencedetect` no microfone, o loop começa quando a
fala é detectada (`silence_end`) e para depois de `silence_s` de silêncio
(`silence_start`). Se ninguém falar dentro de `wait_s`, nada é transcrito
(`[voz] nada detectado`) e o agente não é chamado. Os tunables são
parâmetros/constantes de `capture.record_auto`:
- `noise_db=-35` — limiar de `silencedetect` (dB);
- `silence_s=1.0` — silêncio necessário para encerrar a fala;
- `wait_s=8.0` — espera máxima pela primeira fala (sem fala → desiste);
- `max_s=15` — teto absoluto da gravação.

O STT usa VAD (`vad_filter=True`) e descarta áudio sem fala, evitando
alucinações do Whisper em silêncio/ruído.

Push-to-talk (Enter para começar, Enter para parar):

    VOICE_INPUT=ptt python loop.py --voice

Janela fixa de `RECORD_SECONDS` segundos:

    VOICE_INPUT=fixed python loop.py --voice

`VOICE_PTT` (legado) continua valendo: `VOICE_PTT=1` → `ptt`,
`VOICE_PTT=0` → `fixed`; `VOICE_INPUT` tem precedência.

### Wake word e gatilhos

Com `VOICE_ACTIVATION=wake`, o loop ignora falas que não começam com um gatilho declarado. Os gatilhos vivem em `voice/triggers.json` (base) e em `~/.config/jarvis/triggers.json` (override). Cada gatilho tem `phrases` (canônicas, com casamento fuzzy), um `target` (`{"kind":"agent","agent":"chat"}` ou `{"kind":"action","action":"vision|mute|pause|quit|measure"}`) e, opcionalmente, `aliases`, `strip`, `fuzzy` e `enabled`. Editar o arquivo vale no próximo turno (cache por mtime).

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

> **Invariante do `--pure`:** `--pure` desabilita os plugins do projeto,
> incluindo o SafetyGate e as tools `act_*`. Use-o **apenas** com um agente
> **sem tools** (a visão usa o agente tool-less `vision`); assim evita-se o custo
> de carregar plugins sem abrir um buraco de execução. O modo `--do` NÃO usa
> `--pure` porque precisa das tools `act_*` e do gate. A visão (`--see`) também
> não abre buraco: o conteúdo da tela é não-confiável e vai para o agente `vision`.

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
  `$JARVIS_WIN_HOME/tools/ffmpeg/ffmpeg-master-latest-win64-gpl/bin/ffmpeg.exe`
  (`JARVIS_WIN_HOME` default `/mnt/c/Users/Public`; aponte para `/mnt/c/Users/<voce>`
  no `local.conf`); sobrescreva com `FFMPEG_EXE` se o caminho for outro.
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
| `PIPER_OUT_WAV` | `%JARVIS_WIN_HOME%\tools\piper\out.wav` | WAV temporário do piper |
| `FFMPEG_EXE` | caminho do ffmpeg.exe do Windows (acima) | binário de captura |
| `MIC_DEVICE` | `Microphone (FIFINE Microphone)` | nome do device dshow |
| `WHISPER_MODEL` | `base` | modelo do faster-whisper |
| `RECORD_SECONDS` | `5` | duração da gravação por turno (só com `VOICE_INPUT=fixed`) |
| `VOICE_INPUT` | `auto` | modo de entrada: `auto` (fala), `ptt` (Enter/Enter) ou `fixed` (janela) |
| `VOICE_PTT` | — | legado: `1` → `ptt`, `0` → `fixed` (precedido por `VOICE_INPUT`) |
| `VOICE_ACTIVATION` | `free` | modo de ativação: `free` (responde a qualquer fala) ou `wake` (exige palavra-gatilho em `triggers.json`) |
| `JARVIS_TRIGGERS` | — | caminho de um `triggers.json` de override (mesclado por `name` sobre a base do repo) |
| `VOICE_LANGUAGE` | `pt` | idioma do STT |
| `POWERSHELL_EXE` | `powershell.exe` | PowerShell para o TTS (SAPI) |
| `OPENCODE_BIN` | `~/.opencode/bin/opencode` | binário do agente |
| `VOICE_TIMEOUT_S` | `300` | timeout do agente por turno |

## Testes
    . .venv/bin/activate && pytest -q
