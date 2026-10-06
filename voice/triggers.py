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
