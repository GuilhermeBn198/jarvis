import os
from dataclasses import dataclass

DEFAULT_MODEL = "qwen3:8b"
DEFAULT_NUM_CTX = 8192
DEFAULT_TIMEOUT_S = 180


@dataclass(frozen=True)
class Config:
    ollama_host: str
    model: str
    num_ctx: int
    timeout_s: int

    @property
    def chat_url(self) -> str:
        return f"http://{self.ollama_host}/api/chat"


def load_config(env: dict | None = None) -> Config:
    e = os.environ if env is None else env
    host = (e.get("OLLAMA_HOST") or "").strip()
    if not host:
        raise ValueError("OLLAMA_HOST nao definido (ex.: 172.19.32.1:11434)")
    for scheme in ("http://", "https://"):
        if host.startswith(scheme):
            host = host[len(scheme):]
    host = host.rstrip("/")
    return Config(
        ollama_host=host,
        model=e.get("DELEGATE_LOCAL_MODEL", DEFAULT_MODEL),
        num_ctx=int(e.get("DELEGATE_LOCAL_NUM_CTX", DEFAULT_NUM_CTX)),
        timeout_s=int(e.get("DELEGATE_LOCAL_TIMEOUT_S", DEFAULT_TIMEOUT_S)),
    )
