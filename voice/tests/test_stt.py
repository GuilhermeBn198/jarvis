import pytest
from config import Config
import stt as stt_mod

CFG = Config(opencode_bin="/x/o", timeout_s=10, whisper_model="base", language="pt")


@pytest.fixture(autouse=True)
def _clear_cache():
    stt_mod._reset_cache()
    yield
    stt_mod._reset_cache()


def _info():
    return type("I", (), {"language": "pt", "duration": 1.0})()


def test_transcribe_joins_segments(monkeypatch):
    class Seg:
        def __init__(self, t): self.text = t
    class Model:
        def transcribe(self, path, **kw):
            return [Seg(" ola"), Seg(" mundo")], _info()
    monkeypatch.setattr(stt_mod, "_load_model", lambda cfg: Model())
    assert stt_mod.transcribe("/tmp/a.wav", config=CFG) == "ola mundo"


def test_empty_vad_result_returns_empty(monkeypatch):
    class Model:
        def transcribe(self, path, **kw):
            return [], _info()
    monkeypatch.setattr(stt_mod, "_load_model", lambda cfg: Model())
    assert stt_mod.transcribe("/tmp/a.wav", config=CFG) == ""


def test_transcribe_enables_vad_and_disables_context(monkeypatch):
    seen = {}

    class Model:
        def transcribe(self, path, **kw):
            seen.update(kw)
            return [], _info()

    monkeypatch.setattr(stt_mod, "_load_model", lambda cfg: Model())
    stt_mod.transcribe("/tmp/a.wav", config=CFG)
    assert seen["vad_filter"] is True
    assert seen["condition_on_previous_text"] is False
    assert seen["language"] == "pt"
    assert seen["beam_size"] == 1


def test_model_is_cached_per_whisper_model(monkeypatch):
    loads = []
    class Model:
        def transcribe(self, path, **kw):
            return [], _info()
    monkeypatch.setattr(stt_mod, "_load_model", lambda cfg: loads.append(cfg.whisper_model) or Model())
    stt_mod.transcribe("/tmp/a.wav", config=CFG)
    stt_mod.transcribe("/tmp/a.wav", config=CFG)
    assert loads == ["base"]
