from loop import voice_loop

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
