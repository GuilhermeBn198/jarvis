import json

import model_selection


class Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def test_catalog_uses_ollama_host_and_marks_cloud_models(monkeypatch):
    seen = []
    monkeypatch.setenv("OLLAMA_HOST", "http://ollama.example:11434/")
    monkeypatch.setattr(model_selection, "urlopen", lambda url, timeout: seen.append((url, timeout)) or Response({"models":[{"name":"qwen3:8b"},{"name":"minimax-m3.1-flash:cloud"}]}))

    assert model_selection.list_ollama_models() == [
        {"name":"minimax-m3.1-flash:cloud","cloud":True},
        {"name":"qwen3:8b","cloud":False},
    ]
    assert seen == [("http://ollama.example:11434/api/tags", 3)]


def test_opencode_environment_adds_all_tags_without_touching_executor(monkeypatch):
    monkeypatch.setattr(model_selection, "list_ollama_models", lambda env=None: [{"name":"model-a","cloud":False},{"name":"model-b:cloud","cloud":True}])
    env = model_selection.opencode_catalog_environment({"KEEP":"value"})

    assert env["KEEP"] == "value"
    config = json.loads(env["OPENCODE_CONFIG_CONTENT"])
    assert config["provider"]["ollama"]["models"] == {"model-a":{"name":"model-a"},"model-b:cloud":{"name":"model-b:cloud"}}
    assert config["provider"]["ollama"]["options"]["baseURL"] == "http://127.0.0.1:11434/v1"
    assert env["OLLAMA_HOST"] == "127.0.0.1:11434"
    assert "agent" not in config


def test_opencode_environment_preserves_existing_inline_configuration(monkeypatch):
    monkeypatch.setattr(model_selection, "list_ollama_models", lambda env=None: [{"name":"model-a","cloud":False}])
    existing = {
        "model": "openai/custom-model",
        "provider": {
            "openai": {"models": {"custom-model": {"name":"Custom"}}},
            "ollama": {"options": {"apiKey":"local-secret", "timeout":1234}, "models": {"old-model": {"name":"Old"}}},
        },
    }

    env = model_selection.opencode_catalog_environment({"OPENCODE_CONFIG_CONTENT": json.dumps(existing)})

    config = json.loads(env["OPENCODE_CONFIG_CONTENT"])
    assert config["model"] == "openai/custom-model"
    assert config["provider"]["openai"] == existing["provider"]["openai"]
    assert config["provider"]["ollama"]["options"]["apiKey"] == "local-secret"
    assert config["provider"]["ollama"]["options"]["timeout"] == 1234
    assert config["provider"]["ollama"]["models"] == {
        "old-model": {"name":"Old"}, "model-a": {"name":"model-a"}
    }


def test_select_model_requires_exact_catalog_tag_and_persists(monkeypatch, tmp_path):
    settings = tmp_path / "settings.json"
    monkeypatch.setenv("JARVIS_SETTINGS", str(settings))
    monkeypatch.setattr(model_selection, "list_ollama_models", lambda: [{"name":"minimax-m3.1-flash:cloud","cloud":True}])

    result = model_selection.select_ollama_model("ollama/minimax-m3.1-flash:cloud")

    assert result == {"selected":"ollama/minimax-m3.1-flash:cloud","cloud":True}
    assert json.loads(settings.read_text())["agent_model"] == result["selected"]
