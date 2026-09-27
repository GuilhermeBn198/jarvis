import io

import pytest

import loop as loop_mod
from config import Config
from loop import _parse_once, main, voice_loop
from tts import VoiceError

CFG = Config(opencode_bin="/x/o", timeout_s=10, record_seconds=1)


def test_voice_loop_orchestrates(monkeypatch):
    calls = []
    monkeypatch.setattr("loop.record", lambda **k: calls.append("record") or "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: calls.append("stt") or "faca algo")
    monkeypatch.setattr("loop.speak", lambda text, **k: calls.append("tts"))

    class Client:
        def ask(self, task, timeout_s=None):
            calls.append("ask")
            return "resposta"
    voice_loop(client=Client(), iterations=1, record_seconds=1)
    assert calls == ["record", "stt", "ask", "tts"]

def test_voice_loop_empty_transcript_skips_agent(monkeypatch):
    calls = []
    monkeypatch.setattr("loop.record", lambda **k: calls.append("record") or "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: calls.append("stt") or "")
    monkeypatch.setattr("loop.speak", lambda text, **k: calls.append("tts"))
    class Client:
        def ask(self, *a, **k):
            calls.append("ask"); return "x"
    voice_loop(client=Client(), iterations=1, record_seconds=1)
    assert "ask" not in calls


def test_voice_loop_forwards_config(monkeypatch):
    seen = {}
    monkeypatch.setattr("loop.record", lambda **k: seen.update(rec=k) or "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: seen.update(stt=k) or "")
    monkeypatch.setattr("loop.speak", lambda text, **k: None)

    class Client:
        def ask(self, task, timeout_s=None):
            return "x"
    voice_loop(client=Client(), iterations=1, record_seconds=1, config=CFG)
    assert seen["rec"]["config"] is CFG
    assert seen["stt"]["config"] is CFG


def test_voice_loop_contains_voiceerror(monkeypatch):
    calls = []
    def boom(**k):
        calls.append("record")
        raise VoiceError("sem mic")
    monkeypatch.setattr("loop.record", boom)
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: calls.append("stt") or "x")
    monkeypatch.setattr("loop.speak", lambda text, **k: calls.append("tts"))
    err = io.StringIO()

    class Client:
        def ask(self, task, timeout_s=None):
            calls.append("ask")
            return "x"
    voice_loop(client=Client(), iterations=2, record_seconds=1, config=CFG, err=err)
    assert calls == ["record", "record"]
    assert "sem mic" in err.getvalue()


def test_parse_once():
    assert _parse_once(["--voice"]) == 0
    assert _parse_once(["--voice", "--once", "3"]) == 3
    assert _parse_once(["--voice", "--once"]) == 1
    assert _parse_once(["--voice", "--once", "x"]) == 1


def test_main_voice_parses_iterations_and_stops(monkeypatch):
    seen = {}
    monkeypatch.setattr(loop_mod, "RunClient", lambda cfg: "client")
    monkeypatch.setattr(loop_mod, "voice_loop", lambda c, iterations=0: seen.update(n=iterations))
    assert main(["--voice", "--once", "1"]) == 0
    assert seen["n"] == 1


def test_main_voice_handles_keyboard_interrupt(monkeypatch):
    monkeypatch.setattr(loop_mod, "RunClient", lambda cfg: "client")
    def boom(c, iterations=0):
        raise KeyboardInterrupt
    monkeypatch.setattr(loop_mod, "voice_loop", boom)
    assert main(["--voice"]) == 0

