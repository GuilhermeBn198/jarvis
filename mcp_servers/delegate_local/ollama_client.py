import json
from typing import Any

import httpx

from config import Config


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, config: Config):
        self._cfg = config

    def chat(self, prompt: str, json_schema: dict | None = None) -> str:
        payload: dict[str, Any] = {
            "model": self._cfg.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": False,
            "options": {"num_ctx": self._cfg.num_ctx},
        }
        if json_schema is not None:
            payload["format"] = json_schema

        try:
            resp = httpx.post(self._cfg.chat_url, json=payload, timeout=self._cfg.timeout_s)
        except httpx.TimeoutException as exc:
            raise OllamaError(
                f"Timeout ({self._cfg.timeout_s}s) ao chamar Ollama em "
                f"{self._cfg.ollama_host} (cold start?)"
            ) from exc
        except httpx.HTTPError as exc:
            raise OllamaError(
                f"Ollama nao respondeu em {self._cfg.ollama_host}: {exc}"
            ) from exc

        if resp.status_code != 200:
            raise OllamaError(f"Ollama respondeu HTTP {resp.status_code}: {resp.text[:200]}")

        try:
            data = resp.json()
        except ValueError as exc:
            raise OllamaError("Resposta do Ollama nao e JSON") from exc

        content = (data.get("message") or {}).get("content")
        if content is None:
            raise OllamaError("Resposta do Ollama sem 'message.content'")

        if json_schema is not None:
            try:
                json.loads(content)
            except ValueError as exc:
                raise OllamaError(
                    "Modelo nao devolveu JSON valido apesar do json_schema"
                ) from exc

        return content
