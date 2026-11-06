"""Validated access to the local Ollama model catalog."""
import json
import os
from settings import save_settings
from urllib.error import URLError
from urllib.request import urlopen


def _ollama_base_url(env: dict) -> str:
    host = env.get("OLLAMA_HOST", "127.0.0.1:11434").strip()
    if not host:
        raise ValueError("OLLAMA_HOST nao definido")
    base = host if "://" in host else f"http://{host}"
    base = base.rstrip("/")
    return base[:-3] if base.endswith("/v1") else base


def list_ollama_models(env: dict | None = None) -> list[dict]:
    url = _ollama_base_url(os.environ if env is None else env) + "/api/tags"
    try:
        with urlopen(url, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, ValueError) as exc:
        raise RuntimeError(f"catalogo Ollama indisponivel: {exc}") from exc
    raw = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(raw, list):
        raise RuntimeError("resposta invalida do catalogo Ollama")
    models = []
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            continue
        name = item["name"].strip()
        if name:
            models.append({"name": name, "cloud": name.endswith(":cloud")})
    return sorted(models, key=lambda model: model["name"].casefold())


def select_ollama_model(model_id: str) -> dict:
    if not isinstance(model_id, str) or not model_id.startswith("ollama/"):
        raise ValueError("modelo invalido; esperado ollama/<tag>")
    tag = model_id[len("ollama/"):]
    if not tag or tag.startswith("/") or tag.endswith("/") or "\x00" in tag:
        raise ValueError("modelo invalido")
    models = list_ollama_models()
    match = next((model for model in models if model["name"] == tag), None)
    if match is None:
        raise ValueError("modelo nao encontrado no catalogo Ollama")
    save_settings({"agent_model": model_id})
    return {"selected": model_id, "cloud": match["cloud"]}


def opencode_catalog_environment(env: dict | None = None) -> dict:
    """Supply every currently installed tag to OpenCode's configured Ollama provider."""
    env = dict(os.environ if env is None else env)
    try:
        models = list_ollama_models(env)
    except (RuntimeError, ValueError):
        return env
    base = _ollama_base_url(env)
    env["OLLAMA_HOST"] = base.removeprefix("http://").removeprefix("https://")
    try:
        content = json.loads(env.get("OPENCODE_CONFIG_CONTENT", "{}"))
    except (TypeError, ValueError):
        # Keep malformed user config intact so OpenCode can report its parse error.
        return env
    if not isinstance(content, dict):
        return env
    providers = content.get("provider")
    if not isinstance(providers, dict):
        providers = {}
    else:
        providers = dict(providers)
    ollama = providers.get("ollama")
    if not isinstance(ollama, dict):
        ollama = {}
    else:
        ollama = dict(ollama)
    options = ollama.get("options")
    if not isinstance(options, dict):
        options = {}
    ollama["options"] = {**options, "baseURL": base + "/v1"}
    configured_models = ollama.get("models")
    if not isinstance(configured_models, dict):
        configured_models = {}
    ollama["models"] = {
        **configured_models,
        **{model["name"]: {"name": model["name"]} for model in models},
    }
    providers["ollama"] = ollama
    content["provider"] = providers
    env["OPENCODE_CONFIG_CONTENT"] = json.dumps(content, separators=(",", ":"))
    return env
