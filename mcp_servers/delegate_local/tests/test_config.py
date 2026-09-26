import pytest
from config import load_config, DEFAULT_MODEL, DEFAULT_NUM_CTX, DEFAULT_TIMEOUT_S


def test_requires_ollama_host():
    with pytest.raises(ValueError):
        load_config({})


def test_defaults():
    cfg = load_config({"OLLAMA_HOST": "172.19.32.1:11434"})
    assert cfg.ollama_host == "172.19.32.1:11434"
    assert cfg.model == DEFAULT_MODEL
    assert cfg.num_ctx == DEFAULT_NUM_CTX
    assert cfg.timeout_s == DEFAULT_TIMEOUT_S


def test_strips_scheme_and_slash():
    cfg = load_config({"OLLAMA_HOST": "http://172.19.32.1:11434/"})
    assert cfg.ollama_host == "172.19.32.1:11434"
    assert cfg.chat_url == "http://172.19.32.1:11434/api/chat"


def test_env_overrides():
    cfg = load_config({
        "OLLAMA_HOST": "h:1",
        "DELEGATE_LOCAL_MODEL": "m",
        "DELEGATE_LOCAL_NUM_CTX": "4096",
        "DELEGATE_LOCAL_TIMEOUT_S": "30",
    })
    assert (cfg.model, cfg.num_ctx, cfg.timeout_s) == ("m", 4096, 30)
