import pytest
from config import Config
import stt as stt_mod

CFG = Config(opencode_bin="/x/o", timeout_s=10, whisper_model="base", language="pt")

def test_transcribe_joins_segments(monkeypatch):
    class Seg:
        def __init__(self, t): self.text = t
    class Model:
        def transcribe(self, path, language=None, beam_size=1):
            return [Seg(" ola"), Seg(" mundo")], type("I", (), {"language": "pt", "duration": 1.0})()
    monkeypatch.setattr(stt_mod, "_load_model", lambda cfg: Model())
    assert stt_mod.transcribe("/tmp/a.wav", config=CFG) == "ola mundo"

def test_empty_file_returns_empty(monkeypatch):
    class Model:
        def transcribe(self, path, language=None, beam_size=1):
            return [], type("I", (), {"language": "pt", "duration": 0.0})()
    monkeypatch.setattr(stt_mod, "_load_model", lambda cfg: Model())
    assert stt_mod.transcribe("/tmp/a.wav", config=CFG) == ""
