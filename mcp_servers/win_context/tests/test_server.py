import base64
import importlib
import re

import context as ctx
from mcp.server.mcpserver.exceptions import ToolError

@pytest.fixture(autouse=True)
def windows_contract(monkeypatch):
    monkeypatch.setenv("JARVIS_PLATFORM", "wsl")



def _server():
    import server

    return importlib.reload(server)


def test_win_list_text_usa_contexto(monkeypatch):
    s = _server()
    monkeypatch.setattr(ctx, "list_windows", lambda: [ctx.Window(7, "T", "p")])
    out = s.win_list_text()
    assert "7\tp\tT" in out


# --- #26: erro real com causa no formato unico dos plugins -------------------


def _erro_powershell(stderr="erro real", code=1):
    def boom(*_a, **_k):
        raise ctx.WinContextError("powershell falhou", exit_code=code, stderr=stderr)

    return boom


def test_win_list_text_erro_vira_runtime_com_formato(monkeypatch):
    s = _server()
    monkeypatch.setattr(ctx, "list_windows", _erro_powershell("EnumWindows falhou"))
    with pytest.raises(RuntimeError) as ei:
        s.win_list_text()
    assert (
        str(ei.value)
        == "erro em win_list_text (etapa: powershell): exit code 1: EnumWindows falhou"
    )


def test_win_list_text_erro_sem_exit_code_ainda_formata(monkeypatch):
    s = _server()

    def boom():
        raise ctx.WinContextError("sem powershell")

    monkeypatch.setattr(ctx, "list_windows", boom)
    with pytest.raises(RuntimeError) as ei:
        s.win_list_text()
    assert str(ei.value) == "erro em win_list_text (etapa: powershell): sem powershell"


def test_win_tree_text_valida_hwnd():
    s = _server()
    with pytest.raises(ValueError):
        s.win_tree_text(0)
    with pytest.raises(ValueError):
        s.win_tree_text(1, max_nodes=0)


def test_win_tree_text_formata(monkeypatch):
    s = _server()
    monkeypatch.setattr(ctx, "_default_run", lambda script: "Document\tOla\nButton\tOK\n")
    out = s.win_tree_text(123)
    assert out == "Document\tOla\nButton\tOK"


def test_processes_filter_escapa_aspas(monkeypatch):
    s = _server()
    seen = {}
    monkeypatch.setattr(ctx, "_default_run", lambda script: seen.setdefault("s", script) or "x")
    s.win_processes_text("no'te")
    assert "no''te" in seen["s"]


def test_clipboard_vazio_mensagem(monkeypatch):
    s = _server()
    monkeypatch.setattr(ctx, "_default_run", lambda script: "")
    assert s.win_clipboard_text() == "(clipboard vazio)"


def test_linux_windows_alias_selects_native_backend(monkeypatch):
    s=_server()
    monkeypatch.setenv("JARVIS_PLATFORM","linux")
    monkeypatch.setattr(s.linux,"list_windows",lambda:[{"id":"atspi:opaque","process":"gtk","title":"ação"}])
    monkeypatch.setattr(ctx,"list_windows",lambda:pytest.fail("Windows backend invoked"))
    assert s.win_list_text()=="atspi:opaque\tgtk\tação"
    with pytest.raises(ToolError,match="hwnd"):
        s.win_tree_text(123)


@pytest.mark.parametrize(
    ("tool_name", "message"),
    [
        ("desktop_list_text", "AT-SPI exige sessao grafica"),
        ("desktop_clipboard_text", "clipboard exige sessao grafica"),
        ("desktop_tree_text", "AT-SPI exige sessao grafica"),
    ],
)
def test_linux_desktop_context_reports_unsupported_when_headless(monkeypatch, tool_name, message):
    s = _server()
    monkeypatch.setenv("JARVIS_PLATFORM", "linux")
    monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("DISPLAY", raising=False)

    with pytest.raises(ToolError, match=message):
        if tool_name == "desktop_tree_text":
            s.desktop_tree_text("atspi:opaque")
        else:
            getattr(s, tool_name)()
