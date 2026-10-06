"""Matcher puro de frases-gatilho (wake words / workflows).

Nao faz I/O no nucleo de matching: `match()` recebe um `Registry` ja carregado.
Sem dependencia nova (so stdlib).
"""

import json
import os
import re
import sys
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


def _target_from_dict(d: dict) -> Target:
    kind = str(d.get("kind", "")).strip().lower()
    if kind == "agent":
        name = str(d.get("agent", "")).strip()
    elif kind == "action":
        name = str(d.get("action", "")).strip()
    else:
        raise ValueError(f"target.kind invalido: {kind!r}")
    if not name:
        raise ValueError("target sem nome")
    return Target(kind, name)


def _trigger_from_dict(d: dict) -> Trigger:
    name = str(d.get("name", "")).strip()
    phrases = tuple(str(p).strip() for p in (d.get("phrases") or []) if str(p).strip())
    if not name or not phrases:
        raise ValueError("gatilho sem name/phrases")
    target = _target_from_dict(d.get("target") or {})
    aliases = tuple(str(a).strip() for a in (d.get("aliases") or []) if str(a).strip())
    return Trigger(
        name=name,
        phrases=phrases,
        target=target,
        aliases=aliases,
        strip=bool(d.get("strip", True)),
        fuzzy=(None if d.get("fuzzy") is None else int(d["fuzzy"])),
        enabled=bool(d.get("enabled", True)),
    )


def _registry_from_dict(data: dict, err=None) -> Registry:
    triggers: list[Trigger] = []
    for item in (data.get("triggers") or []):
        if not isinstance(item, dict):
            _warn(err, f"gatilho descartado (nao e objeto): {item!r}")
            continue
        try:
            triggers.append(_trigger_from_dict(item))
        except (TypeError, ValueError) as exc:
            _warn(err, f"gatilho descartado ({exc}): {item!r}")
    default = None
    if data.get("default"):
        try:
            default = _target_from_dict(data["default"])
        except (TypeError, ValueError) as exc:
            _warn(err, f"default descartado ({exc})")
    fuzzy = data.get("fuzzy")
    if fuzzy is not None:
        try:
            fuzzy = int(fuzzy)
        except (TypeError, ValueError) as exc:
            _warn(err, f"fuzzy invalido ({exc}): {fuzzy!r}")
            fuzzy = None
    return Registry(
        triggers=tuple(triggers),
        default=default,
        fuzzy=fuzzy,
    )


def _warn(err, msg: str) -> None:
    stream = err if err is not None else sys.stderr
    try:
        stream.write(f"[triggers] {msg}\n")
        stream.flush()
    except Exception:
        pass


def _read_registry(path: str | None, err=None) -> Registry | None:
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        _warn(err, f"nao foi possivel ler {path}: {exc}")
        return None
    if not isinstance(data, dict):
        _warn(err, f"{path}: conteudo nao e um objeto JSON")
        return None
    try:
        return _registry_from_dict(data, err)
    except Exception as exc:
        _warn(err, f"{path}: registry invalido ({exc})")
        return None


def _merge(base: Registry, override: Registry) -> Registry:
    by_name = {t.name: t for t in base.triggers}
    for t in override.triggers:
        by_name[t.name] = t
    return Registry(
        triggers=tuple(by_name.values()),
        default=override.default if override.default is not None else base.default,
        fuzzy=override.fuzzy if override.fuzzy is not None else base.fuzzy,
    )


DEFAULT_REGISTRY = Registry(
    triggers=(
        Trigger("chat", ("jarvis",), Target("agent", "chat")),
        Trigger("vision", ("olha", "veja"), Target("action", "vision")),
        Trigger("act", ("faz", "executa"), Target("agent", "act")),
        Trigger("mute", ("silencia", "mudo"), Target("action", "mute")),
        Trigger("pause", ("pausa",), Target("action", "pause")),
    ),
    default=Target("agent", "chat"),
    fuzzy=1,
)

_CACHE: dict[tuple, tuple[float | None, Registry]] = {}


def _reset_cache() -> None:
    _CACHE.clear()


def _max_mtime(paths) -> float | None:
    mtimes = []
    for p in paths:
        if not p:
            continue
        try:
            mtimes.append(os.path.getmtime(p))
        except OSError:
            pass
    return max(mtimes) if mtimes else None


def _load_uncached(base_path, override_path, err) -> Registry:
    base = _read_registry(base_path, err)
    if base is None:
        base = DEFAULT_REGISTRY
    if override_path:
        ov = _read_registry(override_path, err)
        if ov is not None:
            base = _merge(base, ov)
    return base


def load_registry(base_path, override_path=None, err=None, use_cache=True) -> Registry:
    if not use_cache:
        return _load_uncached(base_path, override_path, err)
    key = (base_path, override_path)
    mtime = _max_mtime([base_path, override_path])
    hit = _CACHE.get(key)
    if hit is not None and hit[0] == mtime:
        return hit[1]
    reg = _load_uncached(base_path, override_path, err)
    _CACHE[key] = (mtime, reg)
    return reg
