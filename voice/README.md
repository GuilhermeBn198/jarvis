# voice (jarvis Fase C)

Ponte de texto: stdin → agente (opencode) → stdout.

## Rodar
    cd voice
    . .venv/bin/activate
    echo "responda apenas: ok" | python loop.py

## Testes
    . .venv/bin/activate && pytest -q
