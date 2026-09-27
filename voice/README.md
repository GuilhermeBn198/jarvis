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

## Testes
    . .venv/bin/activate && pytest -q
