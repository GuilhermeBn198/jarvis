from config import load_config, DEFAULT_TIMEOUT_S
import pytest

def test_defaults():
    cfg = load_config({})
    assert cfg.opencode_bin.endswith("/.opencode/bin/opencode")
    assert cfg.timeout_s == DEFAULT_TIMEOUT_S

def test_env_overrides():
    cfg = load_config({"OPENCODE_BIN": "/x/opencode", "VOICE_TIMEOUT_S": "42"})
    assert cfg.opencode_bin == "/x/opencode"
    assert cfg.timeout_s == 42

def test_invalid_timeout_raises():
    with pytest.raises(ValueError) as exc:
        load_config({"VOICE_TIMEOUT_S": "abc"})
    assert "VOICE_TIMEOUT_S deve ser inteiro" in str(exc.value)
    assert "abc" in str(exc.value)


def test_invalid_agent_backend_raises():
    with pytest.raises(ValueError) as exc:
        load_config({"AGENT_BACKEND": "nope"})
    assert "AGENT_BACKEND" in str(exc.value)
    assert "nope" in str(exc.value)


def test_invalid_tts_backend_raises():
    with pytest.raises(ValueError) as exc:
        load_config({"TTS_BACKEND": "nope"})
    assert "TTS_BACKEND" in str(exc.value)
    assert "nope" in str(exc.value)


def test_backend_defaults():
    cfg = load_config({})
    assert cfg.agent_backend == "run"
    assert cfg.tts_backend == "sapi"
    assert cfg.server_url == "http://127.0.0.1:4096"
    assert cfg.piper_exe.endswith("piper.exe")
    assert cfg.piper_model.endswith("pt_BR-faber-medium.onnx")
    assert cfg.ffplay_exe.endswith("ffplay.exe")
    assert cfg.piper_out_wav == r"C:\Users\bguil\tools\piper\out.wav"


def test_backend_env_overrides():
    cfg = load_config({
        "AGENT_BACKEND": "serve",
        "TTS_BACKEND": "piper",
        "OPENCODE_SERVER_URL": "http://127.0.0.1:9999",
        "PIPER_EXE": "/x/piper",
        "PIPER_MODEL": "/x/model.onnx",
        "FFPLAY_EXE": "/x/ffplay",
        "PIPER_OUT_WAV": r"D:\out.wav",
    })
    assert cfg.agent_backend == "serve"
    assert cfg.tts_backend == "piper"
    assert cfg.server_url == "http://127.0.0.1:9999"
    assert cfg.piper_exe == "/x/piper"
    assert cfg.piper_model == "/x/model.onnx"
    assert cfg.ffplay_exe == "/x/ffplay"
    assert cfg.piper_out_wav == r"D:\out.wav"
