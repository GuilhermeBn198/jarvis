"""Matcher puro de frases-gatilho (wake words / workflows).

Nao faz I/O no nucleo de matching: `match()` recebe um `Registry` ja carregado.
Sem dependencia nova (so stdlib).
"""

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class Target:
    kind: str  # "agent" | "action"
    name: str


@dataclass(frozen=True)
class Trigger:
    name: str
    phrases: tuple[str, ...]
    target: Target
    aliases: tuple[str, ...] = ()
    strip: bool = True
    fuzzy: int | None = None
    enabled: bool = True


@dataclass(frozen=True)
class Registry:
    triggers: tuple[Trigger, ...] = ()
    default: Target | None = None
    fuzzy: int | None = None


@dataclass(frozen=True)
class Match:
    name: str
    target: Target
    phrase: str
    text: str
    raw: str


def normalize(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _edit_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(
                prev[j] + 1,        # remocao
                cur[j - 1] + 1,     # insercao
                prev[j - 1] + (ca != cb),  # substituicao
            ))
        prev = cur
    return prev[-1]


def _budget(phrase_len: int, fuzzy: int) -> int:
    if phrase_len < 4:
        return 0
    return max(0, min(fuzzy, 2))


def _boundary_ok(t_spaced: str, consumed: int) -> bool:
    pos = [i for i, c in enumerate(t_spaced) if c != " "]
    if consumed == 0 or consumed >= len(pos):
        return True
    between = t_spaced[pos[consumed - 1] + 1:pos[consumed]]
    return " " in between


def _best_prefix_len(t_spaced: str, compact_text: str, compact_phrase: str,
                     budget: int) -> int | None:
    """Comprimento do prefixo do texto (forma compacta) que melhor casa a frase.

    Considera apenas comprimentos que terminam em **fronteira de palavra** e
    cuja distancia de edicao fique no orcamento; prefere menor distancia e,
    no empate, o comprimento mais proximo do da frase (evita consumir o
    comeco da palavra seguinte ou cortar a atual).
    """
    k = len(compact_phrase)
    lo = max(0, k - budget)
    hi = min(len(compact_text), k + budget)
    best_key = None
    best_ln = None
    for ln in range(lo, hi + 1):
        if not _boundary_ok(t_spaced, ln):
            continue
        d = _edit_distance(compact_phrase, compact_text[:ln])
        if d > budget:
            continue
        key = (d, abs(ln - k), ln)
        if best_key is None or key < best_key:
            best_key = key
            best_ln = ln
    return best_ln


def _strip_leading(text: str, n_alnum: int) -> str:
    count = 0
    i = 0
    n = len(text)
    while i < n and count < n_alnum:
        if text[i].isalnum():
            count += 1
        i += 1
    while i < n and not text[i].isalnum():
        i += 1
    return text[i:].strip()


def match(text: str, registry: Registry) -> Match | None:
    if not text or not text.strip():
        return None
    t = normalize(text)
    tc = t.replace(" ", "")
    if not tc:
        return None
    best_key = None
    best = None  # (trigger, phrase, consumed)
    for order, tr in enumerate(registry.triggers):
        if not tr.enabled:
            continue
        fuzzy = tr.fuzzy if tr.fuzzy is not None else (
            registry.fuzzy if registry.fuzzy is not None else 1
        )
        for phrase in (*tr.phrases, *tr.aliases):
            pc = normalize(phrase).replace(" ", "")
            if not pc:
                continue
            consumed = _best_prefix_len(t, tc, pc, _budget(len(pc), fuzzy))
            if consumed is None:
                continue
            key = (-len(pc), order)
            if best_key is None or key < best_key:
                best_key = key
                best = (tr, phrase, consumed)
    if best is None:
        return None
    tr, phrase, consumed = best
    remaining = _strip_leading(text, consumed) if tr.strip else text.strip()
    return Match(name=tr.name, target=tr.target, phrase=phrase, text=remaining, raw=text)
