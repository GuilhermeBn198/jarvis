import httpx
import pytest
from config import Config
from ollama_client import OllamaClient, OllamaError

CFG = Config(ollama_host="h:1", model="qwen3:8b", num_ctx=8192, timeout_s=5)


class _Resp:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _client():
    return OllamaClient(CFG)


def test_success_free_text(monkeypatch):
    seen = {}

    def fake_post(url, json=None, timeout=None):
        seen["url"] = url
        seen["payload"] = json
        return _Resp(payload={"message": {"content": "ola"}})

    monkeypatch.setattr(httpx, "post", fake_post)
    out = _client().chat("diga ola")
    assert out == "ola"
    assert seen["url"] == "http://h:1/api/chat"
    assert seen["payload"]["model"] == "qwen3:8b"
    assert seen["payload"]["think"] is False
    assert seen["payload"]["options"] == {"num_ctx": 8192}
    assert "format" not in seen["payload"]


def test_schema_sets_format(monkeypatch):
    seen = {}

    def fake_post(url, json=None, timeout=None):
        seen["payload"] = json
        return _Resp(payload={"message": {"content": '{"n": 1}'}})

    monkeypatch.setattr(httpx, "post", fake_post)
    schema = {"type": "object", "properties": {"n": {"type": "number"}}}
    out = _client().chat("devolva n", schema)
    assert seen["payload"]["format"] == schema
    assert out == '{"n": 1}'


def test_schema_but_non_json_raises(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp(payload={"message": {"content": "nao json"}}))
    with pytest.raises(OllamaError):
        _client().chat("x", {"type": "object"})


def test_timeout_raises(monkeypatch):
    def fake_post(*a, **k):
        raise httpx.TimeoutException("t")

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(OllamaError):
        _client().chat("x")


def test_http_error_raises(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp(status_code=500, text="boom"))
    with pytest.raises(OllamaError):
        _client().chat("x")


def test_missing_content_raises(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp(payload={"message": {}}))
    with pytest.raises(OllamaError):
        _client().chat("x")
