CODE_OMIT = "bloco de código omitido"
_CODE_FENCE = "```"
_TERMINATORS = ".!?…"
_ABBREV = ("sr", "sra", "dr", "dra", "etc", "ex", "obs", "p", "pag", "fig", "vs", "prof")


class SentenceChunker:
    """Acumula deltas e devolve pedaços faláveis (puro, sem I/O)."""

    def __init__(self, min_chars: int = 15):
        self._min = min_chars
        self._buf = ""
        self._pending = ""
        self._in_fence = False
        self._fence_notified = False

    def feed(self, delta: str) -> list[str]:
        self._buf += delta or ""
        out: list[str] = []
        self._drain(out)
        return out

    def flush(self) -> list[str]:
        out: list[str] = []
        if self._in_fence:
            self._buf = ""
            if not self._fence_notified:
                self._fence_notified = True
                out.append(CODE_OMIT)
        else:
            self._emit(self._buf.strip(), out)
            self._buf = ""
        if self._pending:
            out.append(self._pending)
            self._pending = ""
        return out

    def _emit(self, text: str, out: list[str]) -> None:
        if not text:
            return
        merged = (self._pending + " " + text).strip() if self._pending else text
        if len(merged) < self._min:
            self._pending = merged
            return
        self._pending = ""
        out.append(merged)

    def _drain(self, out: list[str]) -> None:
        while True:
            if self._in_fence:
                idx = self._buf.find(_CODE_FENCE)
                if idx == -1:
                    self._buf = self._buf[-2:]  # guarda possível fence parcial
                    return
                self._buf = self._buf[idx + 3:]
                self._in_fence = False
                if not self._fence_notified:
                    self._fence_notified = True
                    out.append(CODE_OMIT)
                continue
            fence_idx = self._buf.find(_CODE_FENCE)
            term_idx = self._find_terminator()
            if term_idx is not None and (fence_idx == -1 or term_idx < fence_idx):
                self._emit(self._buf[:term_idx + 1].strip(), out)
                self._buf = self._buf[term_idx + 1:].lstrip()
                continue
            if fence_idx != -1:
                self._emit(self._buf[:fence_idx].strip(), out)
                self._buf = self._buf[fence_idx + 3:]
                self._in_fence = True
                continue
            return

    def _find_terminator(self):
        b = self._buf
        for i, ch in enumerate(b):
            if ch not in _TERMINATORS:
                continue
            if i + 1 < len(b) and b[i + 1] not in " \n\t\"')]}":
                continue
            if ch == "." and self._protected(i):
                continue
            return i
        return None

    def _protected(self, i: int) -> bool:
        b = self._buf
        if i > 0 and b[i - 1].isdigit() and i + 1 < len(b) and b[i + 1].isdigit():
            return True
        j = i - 1
        while j >= 0 and b[j].isalpha():
            j -= 1
        return b[j + 1:i].lower() in _ABBREV
