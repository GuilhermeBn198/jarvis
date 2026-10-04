import context as ctx


def test_parse_windows_extrai_jsonlines_e_ignora_ruido():
    out = "\n".join([
        "PS> lixo",
        '{"hwnd":111,"title":"Notepad","process":"notepad"}',
        '{"hwnd":222,"title":"Chrome","process":"chrome"}',
    ])
    wins = ctx.parse_windows(out)
    assert [(w.hwnd, w.title, w.process) for w in wins] == [
        (111, "Notepad", "notepad"),
        (222, "Chrome", "chrome"),
    ]


def test_parse_windows_vazio_sem_json():
    assert ctx.parse_windows("erro qualquer") == []


def test_format_windows_compacto_e_estavel():
    wins = [ctx.Window(1, "A", "app"), ctx.Window(2, "B", "")]
    assert ctx.format_windows(wins) == "1\tapp\tA\n2\t\tB"
    assert ctx.format_windows([]) == "(nenhuma janela visivel)"


def test_list_windows_usa_executor_injetado():
    fake = '{"hwnd":5,"title":"X","process":"p"}'
    wins = ctx.list_windows(run=lambda script: fake)
    assert wins == [ctx.Window(5, "X", "p")]
    # o script reusa EnumWindows (mesmo win_list do jarvis)
    captured = {}
    ctx.list_windows(run=lambda s: captured.setdefault("s", s) and "" or "")
    assert "EnumWindows" in captured["s"]


def test_format_tree_limpa_linhas_vazias():
    assert ctx.format_tree("\n Document\tOla \n\n Button\tOK\n") == "Document\tOla\nButton\tOK"
    assert ctx.format_tree("   ") == "(sem arvore de acessibilidade)"


def test_tree_script_usa_namespace_uia_correto():
    s = ctx._tree_script(123, 10)
    assert "[System.Windows.Automation.AutomationElement]::FromHandle" in s
    assert "System.Management.Automation.AutomationElement" not in s
