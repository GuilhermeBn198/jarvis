"""Converte saida crua do agente em texto natural para ser falado (TTS)."""

import re

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

_FENCE_RE = re.compile(
    r"(?P<fence>```|~~~)[ \t]*[\w#+.\-]*[ \t]*\n(.*?)(?P=fence)",
    re.DOTALL,
)
_UNCLOSED_FENCE_RE = re.compile(
    r"(?:```|~~~)[ \t]*[\w#+.\-]*[ \t]*\n.*$",
    re.DOTALL,
)

_HEADER_RE = re.compile(r"^\s*#{1,6}\s+")
_BLOCKQUOTE_RE = re.compile(r"^\s*>\s?")
_LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+")
_TABLE_SEP_RE = re.compile(r"^\s*\|?[\s:|-]*-[\s:|-]*\|?\s*$")
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")

_BOLD_STAR_RE = re.compile(r"\*\*([^*]+)\*\*")
_BOLD_UNDERSCORE_RE = re.compile(r"__([^_]+)__")
_EM_STAR_RE = re.compile(r"\*([^*\s][^*]*)\*")
_EM_UNDERSCORE_RE = re.compile(r"(?<![A-Za-z0-9])_([^_\s][^_]*)_(?![A-Za-z0-9])")

_TUI_CHROME_RE = re.compile(r"^>\s+\S+\s+[·•|]")

CODE_OMITTED = " bloco de código omitido "


def strip_ansi(text: str) -> str:
    if not isinstance(text, str):
        return text
    try:
        return ANSI_RE.sub("", text)
    except Exception:
        return text


def _is_tui_chrome(line: str) -> bool:
    """Apenas o chrome real do TUI: `> ...` com separador de metadados."""
    stripped = line.lstrip()
    if not stripped.startswith(">"):
        return False
    if " · " in line or " • " in line:
        return True
    return bool(_TUI_CHROME_RE.match(stripped))


def drop_leading_tui(text: str) -> str:
    """Remove apenas as linhas de chrome do TUI (cabecalho `> ...`) no topo."""
    if not isinstance(text, str):
        return text
    lines = text.splitlines()
    i = 0
    while i < len(lines) and (
        not lines[i].strip() or _is_tui_chrome(lines[i])
    ):
        i += 1
    return "\n".join(lines[i:])


def _replace_fences(
    text: str, speak_code: bool, retained: dict[str, str]
) -> str:
    counter = [0]

    def repl(match: "re.Match") -> str:
        body = match.group(2).strip()
        if speak_code:
            token = f"\x00c{counter[0]}\x00"
            counter[0] += 1
            retained[token] = body
            return f" {token} "
        return CODE_OMITTED

    text = _FENCE_RE.sub(repl, text)
    text = _UNCLOSED_FENCE_RE.sub(CODE_OMITTED, text)
    return text


def _clean_line(line: str) -> str | None:
    if _TABLE_SEP_RE.match(line):
        return None
    line = _HEADER_RE.sub("", line)
    line = _BLOCKQUOTE_RE.sub("", line)
    line = _LIST_RE.sub("", line)
    return line


def _demarkup(s: str) -> str:
    """Remove apenas pares de enfase markdown, nunca caracteres soltos."""
    s = _BOLD_STAR_RE.sub(r"\1", s)
    s = _BOLD_UNDERSCORE_RE.sub(r"\1", s)
    s = _EM_STAR_RE.sub(r"\1", s)
    s = _EM_UNDERSCORE_RE.sub(r"\1", s)
    return s


def speechify(text: str, speak_code: bool = False) -> str:
    """Transforma markdown/ANSI em fala natural. Nunca levanta excecao."""
    if not isinstance(text, str):
        return text
    try:
        s = strip_ansi(text)
        s = drop_leading_tui(s)
        retained: dict[str, str] = {}
        s = _replace_fences(s, speak_code, retained)
        lines = []
        for line in s.splitlines():
            cleaned = _clean_line(line)
            if cleaned is not None:
                lines.append(cleaned)
        s = " ".join(lines)
        s = _LINK_RE.sub(r"\1", s)
        s = s.replace("`", "")
        s = _demarkup(s)
        s = s.replace("|", ",")
        s = re.sub(r"\s+", " ", s)
        for token, code in retained.items():
            s = s.replace(token, " " + code + " ")
        s = re.sub(r"\s+", " ", s)
        return s.strip()
    except Exception:
        return text
