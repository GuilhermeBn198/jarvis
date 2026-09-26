# delegate_local

Tool MCP que executa sub-tarefas no modelo local (Ollama GPU).

## Rodar
Requer `OLLAMA_HOST` definido. O opencode sobe o processo via stdio.

    OLLAMA_HOST=172.19.32.1:11434 .venv/bin/python server.py

O servidor deve rodar sob `.venv/bin/python` (o python do sistema não tem o SDK `mcp`).

## Testes
    python3 -m venv .venv && . .venv/bin/activate
    pip install -r requirements-dev.txt
    pytest -q
