import io

import pytest

import loop
import loop as loop_mod
from config import Config

CFG = Config(opencode_bin="/x/o", timeout_s=10, record_seconds=1)


@pytest.fixture(autouse=True)
def _no_convlog(monkeypatch):
    monkeypatch.setattr("loop.log_turn", lambda *a, **k: None)


def test_see_once_uses_capture_and_see(monkeypatch):
    calls = {}
    monkeypatch.setattr(loop, "capture", lambda **k: calls.setdefault("cap", "/mnt/c/x.png") or "/mnt/c/x.png")
    monkeypatch.setattr(loop, "see", lambda p, png, **k: calls.setdefault("see", (p, png)) or "uma tela")
    monkeypatch.setattr(loop, "speak", lambda t, **k: calls.setdefault("tts", t))
    out = io.StringIO()
    loop.see_once("o que tem?", out=out, config=None)
    assert calls["cap"] == "/mnt/c/x.png"
    assert calls["see"][0] == "o que tem?"
    assert "uma tela" in out.getvalue() or calls.get("tts")


def test_voice_trigger_detection():
    assert loop.is_vision_request("olha o que tem na tela", "olha") is True
    assert loop.is_vision_request("qual a capital da franca", "olha") is False


def test_strip_trigger_removes_prefix():
    assert loop.strip_trigger("olha o que tem na tela", "olha") == "o que tem na tela"
    assert loop.strip_trigger("outra pergunta", "olha") == "outra pergunta"


def test_main_see_calls_see_once(monkeypatch):
    seen = {}
    monkeypatch.setattr(loop_mod, "see_once", lambda q, **k: seen.update(q=q))
    assert loop_mod.main(["--see", "o que tem na tela?"]) == 0
    assert seen["q"] == "o que tem na tela?"


def test_voice_loop_routes_vision_trigger(monkeypatch):
    calls = []
    monkeypatch.setattr("loop.record", lambda **k: "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: "olha o que tem na tela")
    monkeypatch.setattr("loop.capture", lambda **k: calls.append("capture") or "/mnt/c/x.png")
    monkeypatch.setattr("loop.see", lambda p, png, **k: calls.append(("see", p)) or "uma tela")
    monkeypatch.setattr("loop.speak", lambda t, **k: calls.append("tts"))

    class Client:
        def ask(self, task, timeout_s=None):
            calls.append("ask")
            return "normal"

    loop.voice_loop(client=Client(), iterations=1, record_seconds=1, config=CFG)
    assert ("see", "o que tem na tela") in calls
    assert "ask" not in calls
