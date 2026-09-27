import os
from dataclasses import dataclass

DEFAULT_OPENCODE_BIN = os.path.expanduser("~/.opencode/bin/opencode")
DEFAULT_TIMEOUT_S = 300


@dataclass(frozen=True)
class Config:
    opencode_bin: str
    timeout_s: int


def load_config(env: dict | None = None) -> Config:
    e = os.environ if env is None else env
    raw_timeout = e.get("VOICE_TIMEOUT_S", DEFAULT_TIMEOUT_S)
    try:
        timeout_s = int(raw_timeout)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"VOICE_TIMEOUT_S deve ser inteiro: {raw_timeout}") from exc
    return Config(
        opencode_bin=e.get("OPENCODE_BIN", DEFAULT_OPENCODE_BIN),
        timeout_s=timeout_s,
    )
