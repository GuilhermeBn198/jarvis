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


def test_win_list_text_erro_vira_runtime(monkeypatch):
    s = _server()

    def boom():
        raise ctx.WinContextError("sem powershell")

    monkeypatch.setattr(ctx, "list_windows", boom)
    with pytest.raises(RuntimeError):
        s.win_list_text()


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


def test_clipboard_write_erro_vira_runtime(monkeypatch):
    s = _server()

    def boom(_script):
        raise ctx.WinContextError("sem powershell")

    monkeypatch.setattr(ctx, "_default_run", boom)
    with pytest.raises(RuntimeError):
        s.win_clipboard_write("ola", confirm=True)
