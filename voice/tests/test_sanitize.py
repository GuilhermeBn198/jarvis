from sanitize import speechify, strip_ansi, drop_leading_tui


def test_strip_ansi():
    assert strip_ansi("\x1b[0mola\x1b[31m") == "ola"


def test_tui_header_dropped():
    raw = "\x1b[0m\n> build \u00b7 deepseek-v4.1-flash\nTudo bem:\n"
    out = speechify(raw)
    assert out == "Tudo bem:"
    assert "build" not in out
    assert "deepseek" not in out


def test_code_fence_omitted():
    raw = "Veja:\n\n```python\nprint(1)\n```\n"
    out = speechify(raw)
    assert "bloco de código omitido" in out
    assert "print(1)" not in out
    assert "```" not in out


def test_code_fence_kept_when_speak_code():
    raw = "Veja:\n```python\nprint(1)\n```\n"
    out = speechify(raw, speak_code=True)
    assert out == "Veja: print(1)"
    assert "```" not in out
    assert "python" not in out


def test_inline_code_backticks_stripped():
    assert speechify("use `git status` agora") == "use git status agora"


def test_bold_headers_links_tables():
    raw = (
        "# Titulo\n"
        "**negrito** e _italico_\n"
        "veja [a doc](https://x.com/a)\n"
        "| a | b |\n"
        "| --- | --- |\n"
        "| 1 | 2 |\n"
        "- item um\n"
        "1. item dois\n"
    )
    out = speechify(raw)
    assert "#" not in out
    assert "**" not in out and "_" not in out and "*" not in out
    assert "negrito e italico" in out
    assert "a doc" in out
    assert "https://x.com/a" not in out
    assert "|" not in out
    assert "---" not in out
    assert "item um item dois" in out


def test_whitespace_collapsed():
    assert speechify("a\n\n\n  b\t\tc ") == "a b c"


def test_idempotent():
    once = speechify("**oi** `x`\n```\nprint(1)\n```")
    assert speechify(once) == once


def test_never_raises_on_weird_input():
    assert speechify(None) is None
    assert speechify(123) == 123
    assert speechify("") == ""


def test_drop_leading_tui_keeps_later_lines():
    assert drop_leading_tui("> head\nlinha\n> outra") == "linha\n> outra"
