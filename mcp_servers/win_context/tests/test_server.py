import base64
import importlib
import re

import pytest

import context as ctx


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
    assert str(ei.value) == "erro em win_list_text (etapa: powershell): exit code 1: EnumWindows falhou"


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


def _nao_deve_rodar(_script):
    raise AssertionError("script nao deveria ser executado")


def test_clipboard_write_recusa_sem_confirm(monkeypatch):
    s = _server()
    monkeypatch.setattr(ctx, "_default_run", _nao_deve_rodar)
    out = s.win_clipboard_write("ola")
    assert out.startswith("recusado:")
    assert "confirm=true" in out


def test_clipboard_write_recusa_texto_vazio(monkeypatch):
    s = _server()
    monkeypatch.setattr(ctx, "_default_run", _nao_deve_rodar)
    out = s.win_clipboard_write("", confirm=True)
    assert out.startswith("recusado:")


def test_clipboard_write_envia_base64_utf8(monkeypatch):
    s = _server()
    seen = {}
    monkeypatch.setattr(ctx, "_default_run", lambda script: seen.setdefault("s", script) or "")
    out = s.win_clipboard_write("Ola 🚀 acao", confirm=True)
    script = seen["s"]
    assert "Ola" not in script
    m = re.search(r"\$b\s*=\s*'([A-Za-z0-9+/=]+)'", script)
    assert m, script
    assert base64.b64decode(m.group(1)).decode("utf-8") == "Ola 🚀 acao"
    assert out.startswith("escrito")


def test_clipboard_write_erro_vira_runtime_com_causa_redigida(monkeypatch):
    s = _server()
    monkeypatch.setattr(ctx, "_default_run", _erro_powershell("Set-Clipboard negado (chave sk-abc123456789)"))
    with pytest.raises(RuntimeError) as ei:
        s.win_clipboard_write("ola", confirm=True)
    msg = str(ei.value)
    assert msg == (
        "erro em win_clipboard_write (etapa: powershell): exit code 1: Set-Clipboard negado (chave [REDACTADO])"
    )
    assert "sk-abc123456789" not in msg


def test_win_tree_text_erro_redige_segredo_e_mostra_hwnd(monkeypatch):
    s = _server()
    monkeypatch.setattr(
        ctx,
        "_default_run",
        _erro_powershell("falha com chave sk-abc123456789 e token ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"),
    )
    with pytest.raises(RuntimeError) as ei:
        s.win_tree_text(123)
    msg = str(ei.value)
    assert msg.startswith("erro em win_tree_text (etapa: powershell; hwnd 123): exit code 1: falha com chave")
    assert "sk-abc123456789" not in msg
    assert "ghp_ABCDEF" not in msg
    assert "[REDACTADO]" in msg


def test_win_clipboard_text_erro_vira_runtime_com_causa(monkeypatch):
    s = _server()
    monkeypatch.setattr(ctx, "_default_run", _erro_powershell("clipboard ocupado por outro app"))
    with pytest.raises(RuntimeError) as ei:
        s.win_clipboard_text()
    assert str(ei.value) == (
        "erro em win_clipboard_text (etapa: powershell): exit code 1: clipboard ocupado por outro app"
    )


def test_win_processes_text_erro_vira_runtime_com_causa(monkeypatch):
    s = _server()
    monkeypatch.setattr(ctx, "_default_run", _erro_powershell("Get-Process falhou"))
    with pytest.raises(RuntimeError) as ei:
        s.win_processes_text()
    assert str(ei.value) == (
        "erro em win_processes_text (etapa: powershell): exit code 1: Get-Process falhou"
    )
