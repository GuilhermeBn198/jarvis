"""Log append-only de turnos de conversa por voz (best-effort)."""

import json
import os
import sys

DEFAULT_VOICE_LOG = os.path.expanduser("~/.local/share/jarvis/voice-log.jsonl")


def log_turn(record: dict, config=None) -> None:
    """Anexa um turno como uma linha JSON. Nunca levanta excecao."""
    try:
        path = getattr(config, "voice_log_path", None) or DEFAULT_VOICE_LOG
        path = os.path.expanduser(str(path))
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:  # best-effort: nunca derruba o loop de voz
        try:
            sys.stderr.write(f"[convlog] falha ao gravar log: {exc}\n")
            sys.stderr.flush()
        except Exception:
            pass
