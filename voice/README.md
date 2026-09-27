# voice (jarvis Fase C)

Ponte de texto: stdin → agente (opencode) → stdout.

## Rodar
    cd /home/guilherme/github/jarvis/voice
    . .venv/bin/activate
    echo "responda apenas: ok" | python loop.py

## Testes
    . .venv/bin/activate && pytest -q
