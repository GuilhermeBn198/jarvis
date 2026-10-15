"""MCP de contexto do Windows em TEXTO (issue #6).

Expõe, como texto, o que o agente precisa saber sobre a área de trabalho do
Windows sem tirar screenshot: janelas abertas, árvore de acessibilidade (UIA) de
uma janela, conteúdo do clipboard e processos. Corta o custo de tokens do
`see_screen`, que fica como fallback para o que a UIA não expõe (jogos, canvas).

Reusa a descoberta de janelas do `win_list` (mesmo P/Invoke).
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

import context as ctx
from tool_error import format_tool_error

mcp = MCPServer("win_context")


@mcp.tool()
def win_list_text() -> str:
    """Lista as janelas visíveis do Windows como texto: hwnd, processo e título.

    Use isto ANTES de agir em segundo plano (para escolher um hwnd) e para saber
    o que está aberto sem gastar tokens com screenshot.
    """
    try:
        return ctx.format_windows(ctx.list_windows())
    except ctx.WinContextError as exc:
        raise RuntimeError(format_tool_error("win_list_text", "powershell", exc)) from exc


@mcp.tool()
def win_tree_text(hwnd: int, max_nodes: int = 200) -> str:
    """Devolve a árvore de acessibilidade (UIA) de uma janela como texto.

    Args:
        hwnd: identificador da janela (de `win_list_text`).
        max_nodes: teto de nós para não estourar tokens (default 200).
    """
    if hwnd <= 0:
        raise ValueError("hwnd invalido")
    if max_nodes <= 0:
        raise ValueError("max_nodes deve ser positivo")
    try:
        raw = ctx._default_run(ctx._tree_script(hwnd, max_nodes))
    except ctx.WinContextError as exc:
        raise RuntimeError(
            format_tool_error("win_tree_text", "powershell", exc, detail=f"hwnd {hwnd}")
        ) from exc
    return ctx.format_tree(raw)


@mcp.tool()
def win_clipboard_text() -> str:
    """Devolve o texto atual do clipboard do Windows (vazio se não houver)."""
    script = "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Clipboard]::GetText()"
    try:
        return ctx._default_run(script).strip() or "(clipboard vazio)"
    except ctx.WinContextError as exc:
        raise RuntimeError(format_tool_error("win_clipboard_text", "powershell", exc)) from exc


@mcp.tool()
def win_clipboard_write(text: str, confirm: bool = False) -> str:
    """Escreve `text` no clipboard do Windows.

    Args:
        text: conteudo a copiar (Unicode OK).
        confirm: precisa ser true — escrita explicita e auditavel.
    """
    if not confirm:
        return "recusado: escrita no clipboard exige confirm=true (escopo explicito e auditavel)"
    if not text:
        return "recusado: texto vazio"
    try:
        ctx._default_run(ctx.clipboard_write_script(text))
    except ctx.WinContextError as exc:
        # O texto do clipboard NAO entra no detalhe (nunca ecoar conteudo).
        raise RuntimeError(format_tool_error("win_clipboard_write", "powershell", exc)) from exc
    return f"escrito no clipboard ({len(text)} caracteres)"


@mcp.tool()
def win_processes_text(name_filter: str = "") -> str:
    """Lista processos do Windows (nome, id, título da janela) como texto.

    Args:
        name_filter: substring opcional do nome do processo (case-insensitive).
    """
    filt = name_filter.replace("'", "''")
    script = (
        "Get-Process | Where-Object { $_.MainWindowTitle -or '$FILT' -eq '' } | "
        "Where-Object { $_.ProcessName -like '*$FILT*' } | "
        "ForEach-Object { \"$($_.ProcessName)`t$($_.Id)`t$($_.MainWindowTitle)\" }"
    ).replace("$FILT", filt)
    try:
        out = ctx._default_run(script).strip()
        return out or "(nenhum processo)"
    except ctx.WinContextError as exc:
        raise RuntimeError(format_tool_error("win_processes_text", "powershell", exc)) from exc


if __name__ == "__main__":
    mcp.run()
