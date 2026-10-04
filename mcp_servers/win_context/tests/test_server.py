import importlib

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
