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
