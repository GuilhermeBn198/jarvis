# Wake word e gatilhos de frase — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar wake word configurável e um registry declarativo de frases → alvo (agente ou ação) no loop de voz.

**Architecture:** Módulo puro `voice/triggers.py` (normalização + casamento fuzzy da frase líder) alimentado por `triggers.json` (base no repo + override do usuário mesclado por `name`). O `voice_loop` consulta o matcher após transcrever e decide: com match → despacha para o alvo; sem match → em `wake` ignora, em `free` usa o alvo default (comportamento atual).

**Tech Stack:** Python stdlib (sem dependência nova), pytest, Tauri/JS estático (overlay).

## Global Constraints

- **Sem dependência nova** (só stdlib Python).
- Testes: `cd voice && ../voice/.venv/bin/python -m pytest -q` (ou `. .venv/bin/activate && pytest -q`).
- Mensagens/comentários em português; identificadores sem acento (padrão do repo).
- `activation` inválido → `ValueError(f"VOICE_ACTIVATION deve ser 'free' ou 'wake': {valor}")` (mesmo padrão dos outros modos).
- Registry ausente/inválido **nunca** derruba o loop: fallback embutido + aviso no stderr.
- Uma task = um commit. Cada task termina com teste passando.
- Spec: `docs/superpowers/specs/2026-10-05-jarvis-wake-word-e-triggers-design.md`.

---

### Task 1: Tipos e normalização (`voice/triggers.py`)

**Files:**
- Create: `voice/triggers.py`
- Test: `voice/tests/test_triggers.py`

**Interfaces:**
- Produces: `Target(kind, name)`, `Trigger(name, phrases, target, aliases=(), strip=True, fuzzy=None, enabled=True)`, `Registry(triggers=(), default=None, fuzzy=None)`, `Match(name, target, phrase, text, raw)`, `normalize(s) -> str`.

- [ ] **Step 1: Write the failing test**

`voice/tests/test_triggers.py`:

```python
from triggers import normalize


def test_normalize_remove_acentos_caixa_e_pontuacao():
    assert normalize("Olha, o JÁrvis!") == "olha o jarvis"


def test_normalize_colapsa_espacos_e_apara():
    assert normalize("  hey   jarvis  ") == "hey jarvis"


def test_normalize_de_string_vazia():
    assert normalize("") == ""
    assert normalize(None) == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd voice && ../voice/.venv/bin/python -m pytest tests/test_triggers.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'triggers'`.

- [ ] **Step 3: Write minimal implementation**

`voice/triggers.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd voice && ../voice/.venv/bin/python -m pytest tests/test_triggers.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add voice/triggers.py voice/tests/test_triggers.py
git commit -m "feat(triggers): tipos e normalizacao de frases"
```

---

### Task 2: Casamento fuzzy da frase líder (`match`)

**Files:**
- Modify: `voice/triggers.py`
- Test: `voice/tests/test_triggers.py`

**Interfaces:**
- Consumes: `normalize`, `Registry`, `Trigger`, `Target`, `Match` (Task 1).
- Produces: `match(text, registry) -> Match | None`.

- [ ] **Step 1: Write the failing test**

Acrescente a `voice/tests/test_triggers.py`:

```python
from triggers import Target, Trigger, Registry, match

REG = Registry(
    triggers=(
        Trigger("chat", ("jarvis",), Target("agent", "chat")),
        Trigger("vision", ("olha", "olha isso"), Target("action", "vision")),
        Trigger("mute", ("silencia",), Target("action", "mute"), strip=False),
    ),
    default=Target("agent", "chat"),
    fuzzy=1,
)


def test_match_exato_remove_a_frase():
    m = match("jarvis, que horas sao", REG)
    assert m is not None
    assert m.name == "chat"
    assert m.target == Target("agent", "chat")
    assert m.text == "que horas sao"


def test_match_fuzzy_tolera_erro_do_whisper():
    assert match("jarves que horas sao", REG).name == "chat"
    assert match("já vis, tudo bem", REG).name == "chat"


def test_frase_curta_nao_casa_fora_do_orcamento():
    # "olha" (4) tem orcamento 1; "olho" (d=1) casa, mas "joia" nao.
    assert match("olho isso", REG).name == "vision"
    assert match("joia isso", REG) is None


def test_fronteira_de_palavra_evita_casar_no_meio():
    assert match("jarviscoisa", REG) is None


def test_frase_mais_longa_vence():
    m = match("olha isso agora", REG)
    assert m.phrase == "olha isso"
    assert m.text == "agora"


def test_strip_false_preserva_o_texto():
    m = match("silencia", REG)
    assert m.name == "mute"
    assert m.text == "silencia"


def test_texto_vazio_retorna_none():
    assert match("", REG) is None
    assert match("   ", REG) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd voice && ../voice/.venv/bin/python -m pytest tests/test_triggers.py -q`
Expected: FAIL — `ImportError: cannot import name 'match'`.

- [ ] **Step 3: Write minimal implementation**

Acrescente ao fim de `voice/triggers.py`:

```python
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


def _fuzzy_prefix(compact_text: str, compact_phrase: str, budget: int) -> int | None:
    """Menor distancia entre a frase e um prefixo do texto; devolve o
    comprimento consumido, ou None se a distancia minima passa do orcamento."""
    k = len(compact_phrase)
    lo = max(0, k - budget)
    hi = min(len(compact_text), k + budget)
    best_len = None
    best_d = budget + 1
    for ln in range(lo, hi + 1):
        d = _edit_distance(compact_phrase, compact_text[:ln])
        if d < best_d:
            best_d = d
            best_len = ln
    if best_len is None or best_d > budget:
        return None
    return best_len


def _boundary_ok(t_spaced: str, consumed: int) -> bool:
    pos = [i for i, c in enumerate(t_spaced) if c != " "]
    if consumed == 0 or consumed >= len(pos):
        return True
    between = t_spaced[pos[consumed - 1] + 1:pos[consumed]]
    return " " in between


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
            consumed = _fuzzy_prefix(tc, pc, _budget(len(pc), fuzzy))
            if consumed is None or not _boundary_ok(t, consumed):
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd voice && ../voice/.venv/bin/python -m pytest tests/test_triggers.py -q`
Expected: PASS (10 passed).

- [ ] **Step 5: Commit**

```bash
git add voice/triggers.py voice/tests/test_triggers.py
git commit -m "feat(triggers): casamento fuzzy da frase lider"
```

---

### Task 3: Carregamento do registry + `triggers.json`

**Files:**
- Modify: `voice/triggers.py`
- Create: `voice/triggers.json`
- Test: `voice/tests/test_triggers.py`

**Interfaces:**
- Consumes: tipos (Task 1).
- Produces: `_target_from_dict(d)`, `_trigger_from_dict(d)`, `_registry_from_dict(data, err)`, `load_registry(base_path, override_path=None, err=None, use_cache=True) -> Registry`, `DEFAULT_REGISTRY`, `_reset_cache()`.

- [ ] **Step 1: Write the failing test**

Acrescente a `voice/tests/test_triggers.py`:

```python
import json
from triggers import load_registry, DEFAULT_REGISTRY

BASE = {
    "version": 1, "fuzzy": 1,
    "default": {"kind": "agent", "agent": "chat"},
    "triggers": [
        {"name": "chat", "phrases": ["jarvis"], "target": {"kind": "agent", "agent": "chat"}},
        {"name": "vision", "phrases": ["olha"], "target": {"kind": "action", "action": "vision"}},
    ],
}


def _write(tmp_path, name, data):
    p = tmp_path / name
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(p)


def test_load_registry_le_base(tmp_path):
    reg = load_registry(_write(tmp_path, "b.json", BASE), use_cache=False)
    assert [t.name for t in reg.triggers] == ["chat", "vision"]
    assert reg.default == Target("agent", "chat")


def test_load_registry_merge_por_name(tmp_path):
    base = _write(tmp_path, "b.json", BASE)
    override = _write(tmp_path, "u.json", {
        "triggers": [
            {"name": "act", "phrases": ["faz"], "target": {"kind": "agent", "agent": "act"}},
            {"name": "vision", "phrases": ["veja"], "target": {"kind": "action", "action": "vision"}},
        ]
    })
    reg = load_registry(base, override, use_cache=False)
    by = {t.name: t for t in reg.triggers}
    assert by["act"].phrases == ("faz",)          # adicionado
    assert by["vision"].phrases == ("veja",)      # sobrescrito
    assert by["chat"].phrases == ("jarvis",)      # base preservada


def test_load_registry_arquivo_invalido_usa_fallback(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{ nao json", encoding="utf-8")
    reg = load_registry(str(bad), use_cache=False)
    assert reg is DEFAULT_REGISTRY
    assert "registry" in capsys.readouterr().err.lower()


def test_load_registry_gatilho_invalido_e_descartado(tmp_path, capsys):
    base = _write(tmp_path, "b.json", {
        "triggers": [
            {"name": "ok", "phrases": ["oi"], "target": {"kind": "agent", "agent": "chat"}},
            {"name": "ruim", "phrases": ["x"], "target": {"kind": "nope", "agent": "chat"}},
            {"name": "sem_frase", "phrases": [], "target": {"kind": "agent", "agent": "chat"}},
        ]
    })
    reg = load_registry(base, use_cache=False)
    assert [t.name for t in reg.triggers] == ["ok"]
    assert "descartado" in capsys.readouterr().err
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd voice && ../voice/.venv/bin/python -m pytest tests/test_triggers.py -q`
Expected: FAIL — `ImportError: cannot import name 'load_registry'`.

- [ ] **Step 3: Write minimal implementation**

No topo de `voice/triggers.py`, acrescente aos imports:

```python
import json
import os
import sys
```

E **ao fim** do arquivo, acrescente:

```python
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
    return Registry(
        triggers=tuple(triggers),
        default=default,
        fuzzy=(None if fuzzy is None else int(fuzzy)),
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
    return _registry_from_dict(data, err)


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
```

`voice/triggers.json`:

```json
{
  "version": 1,
  "fuzzy": 1,
  "default": { "kind": "agent", "agent": "chat" },
  "triggers": [
    { "name": "chat",   "phrases": ["jarvis"],           "target": { "kind": "agent",  "agent": "chat" } },
    { "name": "vision", "phrases": ["olha", "veja"],     "target": { "kind": "action", "action": "vision" } },
    { "name": "act",    "phrases": ["faz", "executa"],   "target": { "kind": "agent",  "agent": "act" } },
    { "name": "mute",   "phrases": ["silencia", "mudo"], "target": { "kind": "action", "action": "mute" } },
    { "name": "pause",  "phrases": ["pausa"],            "target": { "kind": "action", "action": "pause" } }
  ]
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd voice && ../voice/.venv/bin/python -m pytest tests/test_triggers.py -q`
Expected: PASS (14 passed).

- [ ] **Step 5: Commit**

```bash
git add voice/triggers.py voice/triggers.json voice/tests/test_triggers.py
git commit -m "feat(triggers): load_registry com merge por name e fallback"
```

---

### Task 4: `activation` e `triggers_*` no config

**Files:**
- Modify: `voice/config.py`
- Test: `voice/tests/test_config.py`

**Interfaces:**
- Produces: `Config.activation: str`, `Config.triggers_base: str`, `Config.triggers_override: str | None`; `ACTIVATIONS`, `DEFAULT_ACTIVATION`, `DEFAULT_TRIGGERS_BASE`, `DEFAULT_TRIGGERS_USER`.

- [ ] **Step 1: Write the failing test**

Acrescente a `voice/tests/test_config.py`:

```python
def test_activation_default_e_env():
    from config import DEFAULT_ACTIVATION
    assert load_config({}).activation == DEFAULT_ACTIVATION
    assert load_config({"VOICE_ACTIVATION": "WAKE"}).activation == "wake"


def test_activation_invalido_raises():
    with pytest.raises(ValueError) as exc:
        load_config({"VOICE_ACTIVATION": "nope"})
    assert "VOICE_ACTIVATION" in str(exc.value)
    assert "nope" in str(exc.value)


def test_triggers_paths_defaults_e_env():
    cfg = load_config({})
    assert cfg.triggers_base.endswith("voice/triggers.json")
    assert cfg.triggers_override is None
    assert load_config({"JARVIS_TRIGGERS": "/x/t.json"}).triggers_override == "/x/t.json"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd voice && ../voice/.venv/bin/python -m pytest tests/test_config.py -q`
Expected: FAIL — `AttributeError: 'Config' object has no attribute 'activation'`.

- [ ] **Step 3: Write minimal implementation**

Em `voice/config.py`, junto das outras constantes:

```python
DEFAULT_ACTIVATION = "free"
ACTIVATIONS = ("free", "wake")
DEFAULT_TRIGGERS_BASE = os.path.join(DEFAULT_PROJECT_ROOT, "voice", "triggers.json")
DEFAULT_TRIGGERS_USER = os.path.expanduser("~/.config/jarvis/triggers.json")
```

No `@dataclass(frozen=True) class Config`, após `heartbeat`:

```python
    activation: str = DEFAULT_ACTIVATION
    triggers_base: str = DEFAULT_TRIGGERS_BASE
    triggers_override: str | None = None
```

Em `load_config`, antes do `return Config(...)`:

```python
    activation = str(
        e.get("VOICE_ACTIVATION", settings.get("activation", DEFAULT_ACTIVATION))
    ).strip().lower()
    if activation not in ACTIVATIONS:
        raise ValueError(
            f"VOICE_ACTIVATION deve ser 'free' ou 'wake': {activation}"
        )
    triggers_base = DEFAULT_TRIGGERS_BASE
    triggers_override = str(e.get("JARVIS_TRIGGERS", "")).strip()
    if not triggers_override and os.path.exists(DEFAULT_TRIGGERS_USER):
        triggers_override = DEFAULT_TRIGGERS_USER
    triggers_override = triggers_override or None
```

E no construtor `Config(...)`, ao final:

```python
        activation=activation,
        triggers_base=triggers_base,
        triggers_override=triggers_override,
```

> `settings.get("activation", ...)` só entra depois que a Task 5 adiciona a chave; como `load_settings` filtra por `SETTINGS_KEYS`, um arquivo com `activation` é ignorado até lá (sem erro).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd voice && ../voice/.venv/bin/python -m pytest tests/test_config.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add voice/config.py voice/tests/test_config.py
git commit -m "feat(config): activation (free|wake) e caminhos do triggers.json"
```

---

### Task 5: `activation` no settings/overlay backend

**Files:**
- Modify: `voice/settings.py`
- Test: `voice/tests/test_settings.py`

**Interfaces:**
- Consumes: `Config.activation` (Task 4).
- Produces: `activation` aceito em `CHOICE_KEYS`/`SETTINGS_KEYS`.

- [ ] **Step 1: Write the failing test**

Acrescente a `voice/tests/test_settings.py`:

```python
def test_save_settings_activation_validada(tmp_path):
    p = str(tmp_path / "s.json")
    out = save_settings({"activation": "WAKE"}, path=p)
    assert out["activation"] == "wake"


def test_save_settings_activation_invalida_descartada(tmp_path):
    p = str(tmp_path / "s.json")
    out = save_settings({"activation": "nope"}, path=p)
    assert "activation" not in out
    assert "activation" in SETTINGS_KEYS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd voice && ../voice/.venv/bin/python -m pytest tests/test_settings.py -q`
Expected: FAIL — a chave é descartada (`"activation" not in out`).

- [ ] **Step 3: Write minimal implementation**

Em `voice/settings.py`, no dicionário `CHOICE_KEYS`:

```python
CHOICE_KEYS = {
    "input_mode": ("auto", "ptt", "fixed"),
    "tts_backend": ("piper", "sapi"),
    "activation": ("free", "wake"),
}
```

(Nada mais: `SETTINGS_KEYS` já deriva de `CHOICE_KEYS`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd voice && ../voice/.venv/bin/python -m pytest tests/test_settings.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add voice/settings.py voice/tests/test_settings.py
git commit -m "feat(settings): expoe activation (free|wake)"
```

---

### Task 6: Integração no `voice_loop` (gate + dispatch)

**Files:**
- Modify: `voice/loop.py`
- Test: `voice/tests/test_voice_loop.py`

**Interfaces:**
- Consumes: `match`, `load_registry`, `Registry`, `Target` (Tasks 2–3); `Config.activation`, `Config.triggers_base`, `Config.triggers_override` (Task 4).
- Produces: `_client_for(cfg, agent)`.

- [ ] **Step 1: Write the failing test**

Acrescente a `voice/tests/test_voice_loop.py`:

```python
from triggers import Target, Trigger, Registry

VISION_REG = Registry(
    triggers=(
        Trigger("chat", ("jarvis",), Target("agent", "chat")),
        Trigger("vision", ("olha",), Target("action", "vision")),
        Trigger("mute", ("silencia",), Target("action", "mute")),
        Trigger("act", ("faz",), Target("agent", "act")),
    ),
    default=Target("agent", "chat"),
    fuzzy=1,
)

WAKE_CFG = Config(opencode_bin="/x/o", timeout_s=10, record_seconds=1,
                  input_mode="fixed", activation="wake")


def _patch_loop(monkeypatch, transcript, registry=None):
    monkeypatch.setattr("loop.record", lambda **k: "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: transcript)
    monkeypatch.setattr("loop.load_registry", lambda *a, **k: (registry or VISION_REG))
    monkeypatch.setattr("loop.log_turn", lambda *a, **k: None)


def test_wake_ignora_sem_gatilho(monkeypatch):
    calls = []
    _patch_loop(monkeypatch, "uma conversa qualquer")

    class Client:
        def ask(self, *a, **k):
            calls.append("ask")
            return "x"
    monkeypatch.setattr("loop.speak", lambda *a, **k: calls.append("tts"))
    voice_loop(client=Client(), iterations=1, record_seconds=1, config=WAKE_CFG)
    assert calls == []


def test_free_cai_no_default(monkeypatch):
    seen = []
    _patch_loop(monkeypatch, "uma conversa qualquer")
    monkeypatch.setattr("loop.speak", lambda *a, **k: None)

    class Client:
        def ask(self, task, timeout_s=None):
            seen.append(task)
            return "ok"
    voice_loop(client=Client(), iterations=1, record_seconds=1, config=CFG)
    assert seen == ["uma conversa qualquer"]


def test_frase_de_visao_roteia_para_see_once(monkeypatch):
    seen = []
    _patch_loop(monkeypatch, "olha isso agora")
    monkeypatch.setattr("loop.see_once", lambda prompt, **k: seen.append(prompt))
    monkeypatch.setattr("loop.speak", lambda *a, **k: None)

    class Client:
        def ask(self, *a, **k):
            raise AssertionError("nao deve chamar o agente")
    voice_loop(client=Client(), iterations=1, record_seconds=1, config=CFG)
    assert seen == ["isso agora"]


def test_agente_roteado_usa_client_do_alvo(monkeypatch):
    seen = []
    _patch_loop(monkeypatch, "faz algo")
    monkeypatch.setattr("loop.speak", lambda *a, **k: None)

    class ActClient:
        def ask(self, task, timeout_s=None):
            seen.append(("act", task))
            return "feito"

    class ChatClient:
        def ask(self, *a, **k):
            raise AssertionError("nao deve usar o client default")
    monkeypatch.setattr("loop.make_client", lambda cfg: ActClient())
    voice_loop(client=ChatClient(), iterations=1, record_seconds=1, config=CFG)
    assert seen == [("act", "algo")]


def test_acao_mute_alterna_estado(monkeypatch):
    flags = []

    class Hub:
        def set_flags(self, **k):
            flags.append(k)
        def take_command(self):
            return None
        def subscribers(self):
            return 0
        def set(self, *a, **k):
            pass
        def set_level(self, *a, **k):
            pass

    _patch_loop(monkeypatch, "silencia")
    monkeypatch.setattr("loop.speak", lambda *a, **k: None)

    class Client:
        def ask(self, *a, **k):
            raise AssertionError("mute nao chama agente")
    voice_loop(client=Client(), iterations=1, record_seconds=1, config=CFG, hub=Hub())
    assert flags and flags[-1] == {"muted": True, "paused": False}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd voice && ../voice/.venv/bin/python -m pytest tests/test_voice_loop.py -q`
Expected: FAIL — o loop ainda chama o agente para tudo (o teste `test_wake_ignora_sem_gatilho` falha com `ask` chamado).

- [ ] **Step 3: Write minimal implementation**

Em `voice/loop.py`:

1. Troque o import de dataclasses/agent:

```python
from dataclasses import dataclass, replace
```

e, junto dos imports de `agent_client`:

```python
from triggers import load_registry, match as match_trigger, Target
```

Adicione a constante do alvo default logo após os imports:

```python
DEFAULT_TARGET = Target("agent", "chat")
```

2. Adicione o helper (perto de `resolve_client`):

```python
def _client_for(cfg, agent: str):
    """Client para um agente especifico (roteamento por gatilho)."""
    return make_client(replace(cfg, agent=agent))
```

3. No `while` de `voice_loop`, **substitua** o bloco de visão (o trecho que começa em `if is_vision_request(text, cfg.vision_trigger):` e vai até o `continue` antes de `error = None`) por:

```python
        registry = load_registry(
            cfg.triggers_base, cfg.triggers_override, err=err
        )
        m = match_trigger(text, registry)
        if m is None and cfg.activation == "wake":
            err.write("[voz] sem wake word; ignorando\n")
            err.flush()
            consecutive_errors = 0
            _emit(hub, "idle")
            continue
        target = m.target if m is not None else (registry.default or DEFAULT_TARGET)
        payload = m.text if m is not None else text

        if target.kind == "action":
            action = target.name
            if action == "vision":
                _hb("visao")
                try:
                    see_once(payload, err=err, config=cfg, hub=hub)
                except VoiceError as exc:
                    _emit(hub, "error")
                    if _voice_error(exc):
                        return
                    _emit(hub, "idle")
                    continue
                consecutive_errors = 0
                continue
            if action == "measure":
                measure_requested = True
                continue
            if action == "mute":
                muted = not muted
                _publish_flags()
                _emit(hub, "idle")
                continue
            if action == "pause":
                paused = not paused
                _publish_flags()
                _emit(hub, "idle")
                continue
            if action == "quit":
                return
            err.write(f"[voz] acao desconhecida: {action}\n")
            err.flush()
            _emit(hub, "idle")
            continue

        active_client = client
        if target.name and (cfg.agent or "chat") != target.name:
            try:
                active_client = _client_for(cfg, target.name)
            except Exception as exc:  # fronteira: alvo ruim nao derruba o loop
                err.write(f"[voz] agente '{target.name}' indisponivel: {exc}\n")
                err.flush()
                _emit(hub, "error")
                continue
```

4. Troque o uso do client no restante do turno: `_stream_turn(client, ...)` → `_stream_turn(active_client, ...)`; `client.ask(text)` → `active_client.ask(payload)`.

> O log continua com `"transcript": text` (a fala original), e o agente recebe `payload` (sem a frase).

5. Remova as funções `is_vision_request`/`strip_trigger` **somente se** não houver mais referências (rode `grep -rn "is_vision_request\|strip_trigger" voice/`; há testes em `test_loop.py` para elas — se existirem, mantenha as funções).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd voice && ../voice/.venv/bin/python -m pytest tests/test_voice_loop.py tests/test_loop.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add voice/loop.py voice/tests/test_voice_loop.py
git commit -m "feat(loop): gate de wake word e dispatch por gatilho"
```

---

### Task 7: Opção de ativação no overlay

**Files:**
- Modify: `gui/src/index.html`
- Modify: `gui/src/main.js`

**Interfaces:**
- Consumes: chave `activation` no `/settings` (Task 5).

- [ ] **Step 1: Adicione o campo no HTML**

Em `gui/src/index.html`, logo após o bloco `Modo de entrada` (o `<label>` com `id="s-input"`):

```html
      <label>Ativação
        <select id="s-activation">
          <option value="free">free (responde a qualquer fala)</option>
          <option value="wake">wake (exige palavra-gatilho)</option>
        </select>
      </label>
```

- [ ] **Step 2: Ligue no `loadSettings`**

Em `gui/src/main.js`, dentro de `loadSettings()`, junto das outras linhas:

```js
  document.getElementById("s-activation").value = s.activation ?? "free";
```

- [ ] **Step 3: Ligue no `saveSettings`**

Em `gui/src/main.js`, dentro de `saveSettings()`, junto de `body.input_mode = ...`:

```js
  body.activation = document.getElementById("s-activation").value;
```

- [ ] **Step 4: Verificação manual**

Rodar o overlay (`cd gui/src-tauri && cargo run`) ou abrir `gui/src/index.html` servido; abrir Configurações, escolher **wake**, Salvar e reiniciar; confirmar que o `settings.json` do usuário contém `"activation": "wake"`:

Run: `cat ~/.config/jarvis/settings.json`
Expected: contém `"activation": "wake"`.

- [ ] **Step 5: Commit**

```bash
git add gui/src/index.html gui/src/main.js
git commit -m "feat(overlay): opcao de ativacao free|wake"
```

---

### Task 8: Documentação

**Files:**
- Modify: `README.md`
- Modify: `voice/README.md`
- Modify: `docs/backlog.md`

- [ ] **Step 1: README — capacidades**

Em `README.md`, na lista de **Capacidades**, após o item de "Ações em segundo plano", acrescente:

```markdown
- **Wake word e gatilhos de frase:** o modo de ativação é configurável (`VOICE_ACTIVATION=free|wake`). Em `wake`, só responde se a fala começar com uma palavra-gatilho ("jarvis"). Frases → alvo são declaradas em `triggers.json` (base em `voice/triggers.json`; override do usuário em `~/.config/jarvis/triggers.json`, mesclado por `name`) e podem rotear para um agente (`chat`, `act`, ...) ou uma ação do loop (`vision`, `mute`, `pause`, `quit`, `measure`). O casamento é **fuzzy** (tolera erros do Whisper, ex.: "jarves"), sem exigir aliases manuais.
```

- [ ] **Step 2: README — roadmap**

Em `README.md`, na tabela de **Aprimoramentos planejados**, remova a linha do item "Wake word" e registre na linha de **Concluídos** (o item 1 do roadmap passa a ser o `.exe`):

```markdown
Concluídos: wake word + gatilhos de frase (`VOICE_ACTIVATION`, `triggers.json`), orbe reativo ao áudio (v2 do indicador, PR #12), mic preso mitigado (#4), contexto do Windows em texto (#6), arquivos Windows estruturados (#7), timeout da UIA (#8), foco/cursor E2E (#9), zipapp (#1).
```

- [ ] **Step 3: voice/README — env e modos**

Em `voice/README.md`, na tabela de variáveis, acrescente as linhas:

```markdown
| `VOICE_ACTIVATION` | `free` | modo de ativação: `free` (responde a qualquer fala) ou `wake` (exige palavra-gatilho em `triggers.json`) |
| `JARVIS_TRIGGERS` | — | caminho de um `triggers.json` de override (mesclado por `name` sobre a base do repo) |
```

E, na seção de modo de entrada, acrescente um parágrafo curto:

```markdown
### Wake word e gatilhos

Com `VOICE_ACTIVATION=wake`, o loop ignora falas que não começam com um gatilho declarado. Os gatilhos vivem em `voice/triggers.json` (base) e em `~/.config/jarvis/triggers.json` (override). Cada gatilho tem `phrases` (canônicas, com casamento fuzzy), um `target` (`{"kind":"agent","agent":"chat"}` ou `{"kind":"action","action":"vision|mute|pause|quit|measure"}`) e, opcionalmente, `aliases`, `strip`, `fuzzy` e `enabled`. Editar o arquivo vale no próximo turno (cache por mtime).
```

- [ ] **Step 4: Backlog — item 1**

Em `docs/backlog.md`, no item 1 (Otimizar a latência) **não** mexer. No README já foi. Em `docs/backlog.md`, marque o item de wake word como feito onde ele aparece (o roadmap do README é a fonte; se não houver seção própria no backlog, acrescente ao final da seção 6/7 uma nota):

```markdown
**Wake word + gatilhos de frase — FEITO (2026-10-05):** ver spec `docs/superpowers/specs/2026-10-05-jarvis-wake-word-e-triggers-design.md`. Ativação `free|wake`, registry `triggers.json` (fuzzy, merge por `name`), dispatch para agentes/ações.
```

- [ ] **Step 5: Rodar a suíte e commitar**

Run: `cd voice && ../voice/.venv/bin/python -m pytest -q`
Expected: PASS (todos).

```bash
git add README.md voice/README.md docs/backlog.md
git commit -m "docs: wake word e gatilhos de frase"
```

---

## Self-Review

**1. Cobertura do spec:**
- §1 decisões (free|wake, roteamento+ações, triggers.json, fuzzy) → Tasks 2/4/5/6.
- §3.1 registry + merge + fallback + cache mtime → Task 3.
- §3.2 normalize/fuzzy/fronteira/desempate/strip → Tasks 1/2.
- §3.3 integração no loop + `_client_for` + ações → Task 6.
- §3.4 config/settings → Tasks 4/5; overlay → Task 7.
- §4 erros → Task 3 (fallback/aviso) e Task 6 (alvo ruim).
- §5 testes → Tasks 1–6.
- §6/§7 não-objetivos/evolução → nada a fazer.

**2. Placeholder scan:** sem TBD/TODO; todo passo de código tem o código. (O aviso sobre o `_CacheKey` na Task 3 é para o implementador *não* incluí-lo — remova a nota ao transcrever.)

**3. Consistência de tipos:** `match(text, registry)` e `Registry`/`Trigger`/`Target`/`Match` são definidos na Task 1–2 e usados iguais nas Tasks 3/6; `load_registry(base_path, override_path=None, err=None, use_cache=True)` idêntico em Tasks 3/6; `Config.activation/triggers_base/triggers_override` iguais em Tasks 4/6; `_client_for(cfg, agent)` definido e usado na Task 6.
