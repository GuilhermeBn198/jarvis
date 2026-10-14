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
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "voice"))
from platforms import current_platform
import linux_context as linux


def _linux():
    return current_platform() == "linux"


mcp = MCPServer("win_context")


@mcp.tool()
def win_list_text() -> str:
    """Lista as janelas visíveis do Windows como texto: hwnd, processo e título.

    Use isto ANTES de agir em segundo plano (para escolher um hwnd) e para saber
    o que está aberto sem gastar tokens com screenshot.
    """
    if _linux():
        return desktop_list_text()
    try:
        return ctx.format_windows(ctx.list_windows())
    except ctx.WinContextError as exc:
        raise RuntimeError(str(exc)) from exc


@mcp.tool()
def win_tree_text(hwnd: int, max_nodes: int = 200) -> str:
    """Devolve a árvore de acessibilidade (UIA) de uma janela como texto.

    Args:
        hwnd: identificador da janela (de `win_list_text`).
        max_nodes: teto de nós para não estourar tokens (default 200).
    """
    if _linux():
        raise ValueError("hwnd e especifico de Windows; use desktop_tree_text com ID AT-SPI")
    if hwnd <= 0:
        raise ValueError("hwnd invalido")
    if max_nodes <= 0:
        raise ValueError("max_nodes deve ser positivo")
    try:
        raw = ctx._default_run(ctx._tree_script(hwnd, max_nodes))
    except ctx.WinContextError as exc:
        raise RuntimeError(str(exc)) from exc
    return ctx.format_tree(raw)


@mcp.tool()
def win_clipboard_text() -> str:
    """Devolve o texto atual do clipboard do Windows (vazio se não houver)."""
    if _linux():
        return linux.clipboard_text()
    script = "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Clipboard]::GetText()"
    try:
        return ctx._default_run(script).strip() or "(clipboard vazio)"
    except ctx.WinContextError as exc:
        raise RuntimeError(str(exc)) from exc


@mcp.tool()
def win_processes_text(name_filter: str = "") -> str:
    """Lista processos do Windows (nome, id, título da janela) como texto.

    Args:
        name_filter: substring opcional do nome do processo (case-insensitive).
    """
    if _linux():
        return linux.processes(name_filter)
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
        raise RuntimeError(str(exc)) from exc



@mcp.tool()
def desktop_list_text() -> str:
    """Janelas acessiveis Linux (ID AT-SPI) ou janelas Windows (hwnd)."""
    if not _linux():return win_list_text()
    try:
        return "\n".join(f"{w['id']}\t{w['process']}\t{w['title']}" for w in linux.list_windows()) or "(nenhuma janela acessivel)"
    except linux.ContextError as exc:raise RuntimeError(str(exc)) from exc


@mcp.tool()
def desktop_tree_text(window_id: str, max_nodes: int = 200) -> str:
    """Arvore acessivel limitada; ID opaco de desktop_list_text."""
    if _linux():return linux.accessibility_tree(window_id,max_nodes)
    if not window_id.startswith("hwnd:"):raise ValueError("Windows exige ID hwnd:<numero>")
    return win_tree_text(int(window_id[5:]),max_nodes)


@mcp.tool()
def desktop_clipboard_text() -> str:
    """Texto do clipboard da sessao, quando solicitado."""
    return win_clipboard_text()


@mcp.tool()
def desktop_processes_text(name_filter: str = "") -> str:
    """Nomes e IDs dos processos; filtro literal."""
    return win_processes_text(name_filter)

if __name__ == "__main__":
    mcp.run()
