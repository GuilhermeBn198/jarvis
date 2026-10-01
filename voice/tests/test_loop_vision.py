import io

import pytest

import loop
import loop as loop_mod
from config import Config
from sanitize import speechify
from tts import VoiceError

CFG = Config(opencode_bin="/x/o", timeout_s=10, record_seconds=1, input_mode="fixed", ptt=False)


@pytest.fixture(autouse=True)
def _no_convlog(monkeypatch):
    monkeypatch.setattr("loop.log_turn", lambda *a, **k: None)


def test_see_once_uses_capture_and_see(monkeypatch):
    calls = {}

    def fake_capture(**k):
        calls["cap"] = "/mnt/c/x.png"
        return "/mnt/c/x.png"

    def fake_see(prompt, png, **k):
        calls["see"] = (prompt, png)
        return "uma tela"

    monkeypatch.setattr(loop, "capture", fake_capture)
    monkeypatch.setattr(loop, "see", fake_see)
    monkeypatch.setattr(loop, "speak", lambda t, **k: calls.update(tts=t))
    out = io.StringIO()
    loop.see_once("o que tem?", out=out, config=None)
    assert calls["cap"] == "/mnt/c/x.png"
    assert calls["see"][0] == "o que tem?"
    assert "uma tela" in out.getvalue()
    assert calls["tts"] == speechify("uma tela")


def test_voice_trigger_detection():
    assert loop.is_vision_request("olha o que tem na tela", "olha") is True
    assert loop.is_vision_request("olha, me ajuda", "olha") is True
    assert loop.is_vision_request("olhar a lua", "olha") is False
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


def test_main_see_text_prints_without_tts(monkeypatch):
    monkeypatch.setattr(loop_mod, "capture", lambda **k: "/mnt/c/x.png")
    monkeypatch.setattr(loop_mod, "see", lambda q, png, **k: "uma tela")
    spoke = []
    monkeypatch.setattr(loop_mod, "speak", lambda t, **k: spoke.append(t))
    out = io.StringIO()
    monkeypatch.setattr(loop_mod.sys, "stdout", out)
    assert loop_mod.main(["--see-text", "o que tem?"]) == 0
    assert out.getvalue().strip() == "uma tela"
    assert spoke == []


def test_main_see_text_error_returns_1(monkeypatch):
    monkeypatch.setattr(
        loop_mod, "capture",
        lambda **k: (_ for _ in ()).throw(VoiceError("sem tela")),
    )
    err = io.StringIO()
    monkeypatch.setattr(loop_mod.sys, "stderr", err)
    assert loop_mod.main(["--see-text", "x"]) == 1
    assert "sem tela" in err.getvalue()
