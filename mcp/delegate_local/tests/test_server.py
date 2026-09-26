import pytest

from ollama_client import OllamaError


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "172.19.32.1:11434")


def _import_server():
    import importlib
    import server
    return importlib.reload(server)


def test_empty_prompt_raises():
    server = _import_server()
    with pytest.raises(ValueError):
        server.delegate_local("   ")


def test_invalid_schema_raises():
    server = _import_server()
    with pytest.raises(ValueError):
        server.delegate_local("x", {"bad": object()})


def test_passes_through_to_client(monkeypatch):
    server = _import_server()
    seen = {}

    class FakeClient:
        def chat(self, prompt, json_schema=None):
            seen["prompt"] = prompt
            seen["schema"] = json_schema
            return "ok"

    monkeypatch.setattr(server, "_get_client", lambda: FakeClient())
    out = server.delegate_local("faca x", {"type": "object"})
    assert out == "ok"
    assert seen == {"prompt": "faca x", "schema": {"type": "object"}}


def test_ollama_error_becomes_runtime_error(monkeypatch):
    server = _import_server()

    class FailingClient:
        def chat(self, prompt, json_schema=None):
            raise OllamaError("Ollama fora do ar")

    monkeypatch.setattr(server, "_get_client", lambda: FailingClient())
    with pytest.raises(RuntimeError):
        server.delegate_local("x")


def test_tool_description_guides_model_usage():
    server = _import_server()
    doc = server.delegate_local.__doc__
    assert doc is not None
    assert "LOCAL" in doc
    assert "NAO use" in doc
    assert "raciocinio" in doc
