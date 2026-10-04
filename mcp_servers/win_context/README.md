# win_context — contexto do Windows em TEXTO (MCP)

Expõe a área de trabalho do Windows como **texto** para o agente, cortando o custo
de tokens do `see_screen` (que vira fallback para o que a UIA não expõe).

Tools:
- `win_list_text` — janelas visíveis (hwnd, processo, título).
- `win_tree_text(hwnd, max_nodes=200)` — árvore de acessibilidade (UIA) da janela.
- `win_clipboard_text` — conteúdo atual do clipboard.
- `win_processes_text(name_filter="")` — processos (nome, id, título).

Reusa a descoberta de janelas do `win_list` (mesmo P/Invoke de `.opencode/act/win.ts`).

## Rodar
    python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
    python server.py

## Testes
    . .venv/bin/activate && pip install -r requirements-dev.txt && pytest -q
