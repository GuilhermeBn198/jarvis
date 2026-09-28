"""Converte saida crua do agente em texto natural para ser falado (TTS)."""

import re

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

_FENCE_RE = re.compile(
    r"```[ \t]*[\w#+.\-]*[ \t]*\n(.*?)```",
    re.DOTALL,
)

_HEADER_RE = re.compile(r"^\s*#{1,6}\s+")
_BLOCKQUOTE_RE = re.compile(r"^\s*>\s?")
_LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+")
_TABLE_SEP_RE = re.compile(r"^\s*\|?[\s:|-]*-[\s:|-]*\|?\s*$")
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")

CODE_OMITTED = " bloco de código omitido "


def strip_ansi(text: str) -> str:
    if not isinstance(text, str):
        return text
    try:
        return ANSI_RE.sub("", text)
    except Exception:
        return text


def drop_leading_tui(text: str) -> str:
    """Remove apenas as linhas de chrome do TUI (cabecalho `> ...`) no topo."""
    if not isinstance(text, str):
        return text
    lines = text.splitlines()
    i = 0
    while i < len(lines) and (
        not lines[i].strip() or lines[i].lstrip().startswith(">")
    ):
        i += 1
    return "\n".join(lines[i:])


def _replace_fences(text: str, speak_code: bool) -> str:
    def repl(match: "re.Match") -> str:
        if speak_code:
            return " " + match.group(1).strip() + " "
        return CODE_OMITTED

    return _FENCE_RE.sub(repl, text)


def _clean_line(line: str) -> str | None:
    if _TABLE_SEP_RE.match(line):
        return None
    line = _HEADER_RE.sub("", line)
    line = _BLOCKQUOTE_RE.sub("", line)
    line = _LIST_RE.sub("", line)
    return line


def speechify(text: str, speak_code: bool = False) -> str:
    """Transforma markdown/ANSI em fala natural. Nunca levanta excecao."""
    if not isinstance(text, str):
        return text
    try:
        s = strip_ansi(text)
        s = drop_leading_tui(s)
        s = _replace_fences(s, speak_code)
        lines = []
        for line in s.splitlines():
            cleaned = _clean_line(line)
            if cleaned is not None:
                lines.append(cleaned)
        s = " ".join(lines)
        s = _LINK_RE.sub(r"\1", s)
        s = s.replace("`", "")
        s = s.replace("**", "").replace("__", "")
        s = s.replace("*", "").replace("_", "")
        s = s.replace("|", ",")
        s = re.sub(r"\s+", " ", s)
        return s.strip()
    except Exception:
        return text
