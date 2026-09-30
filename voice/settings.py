import json
import os

DEFAULT_SETTINGS_PATH = os.path.expanduser("~/.config/jarvis/settings.json")

# Chaves que o painel de configuracao do overlay pode editar.
NUMERIC_KEYS = ("noise_db", "silence_s", "wait_s", "max_s", "min_speech_s")
BOOL_KEYS = ("stream_tts",)
STRING_KEYS = ("mic_device",)
SETTINGS_KEYS = NUMERIC_KEYS + BOOL_KEYS + STRING_KEYS


def _path(path: str | None) -> str:
    return path or os.environ.get("JARVIS_SETTINGS", DEFAULT_SETTINGS_PATH)


def load_settings(path: str | None = None) -> dict:
    """Le o arquivo de settings; devolve {} se ausente/invalido."""
    p = _path(path)
    try:
        with open(p, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: data[k] for k in SETTINGS_KEYS if k in data}


def _coerce(key: str, value):
    if key in BOOL_KEYS:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes", "on")
    if key in STRING_KEYS:
        return str(value).strip()
    if key == "noise_db":
        return int(value)
    return float(value)


def save_settings(update: dict, path: str | None = None) -> dict:
    """Mescla `update` (so chaves conhecidas) e persiste; devolve o estado."""
    p = _path(path)
    current = load_settings(p)
    for key, value in (update or {}).items():
        if key not in SETTINGS_KEYS:
            continue
        try:
            current[key] = _coerce(key, value)
        except (TypeError, ValueError):
            continue
    parent = os.path.dirname(p)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(current, fh, indent=2)
    return current
