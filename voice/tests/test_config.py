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


def test_voice_agent_and_log_defaults():
    cfg = load_config({})
    assert cfg.agent == "chat"
    assert cfg.voice_log_path.endswith("voice-log.jsonl")


def test_voice_agent_and_log_env_overrides():
    cfg = load_config({"VOICE_AGENT": "orchestrator", "VOICE_LOG": "/tmp/v.jsonl"})
    assert cfg.agent == "orchestrator"
    assert cfg.voice_log_path == "/tmp/v.jsonl"


def test_backend_defaults():
    cfg = load_config({})
    assert cfg.agent_backend == "serve"
    assert cfg.tts_backend == "piper"
    assert cfg.server_url == "http://127.0.0.1:4096"
    assert cfg.piper_exe.endswith("piper.exe")
    assert cfg.piper_model.endswith("pt_BR-faber-medium.onnx")
    assert cfg.ffplay_exe.endswith("ffplay.exe")
    assert cfg.piper_out_wav == r"C:\Users\bguil\tools\piper\out.wav"


def test_backend_env_overrides():
    cfg = load_config({
        "AGENT_BACKEND": "run",
        "TTS_BACKEND": "sapi",
        "OPENCODE_SERVER_URL": "http://127.0.0.1:9999",
        "PIPER_EXE": "/x/piper",
        "PIPER_MODEL": "/x/model.onnx",
        "FFPLAY_EXE": "/x/ffplay",
        "PIPER_OUT_WAV": r"D:\out.wav",
    })
    assert cfg.agent_backend == "run"
    assert cfg.tts_backend == "sapi"
    assert cfg.server_url == "http://127.0.0.1:9999"
    assert cfg.piper_exe == "/x/piper"
    assert cfg.piper_model == "/x/model.onnx"
    assert cfg.ffplay_exe == "/x/ffplay"
    assert cfg.piper_out_wav == r"D:\out.wav"


def test_input_mode_defaults_auto():
    cfg = load_config({})
    assert cfg.input_mode == "auto"
    assert cfg.ptt is False
    assert cfg.record_seconds == 5


def test_input_mode_env_overrides():
    assert load_config({"VOICE_INPUT": "ptt"}).input_mode == "ptt"
    assert load_config({"VOICE_INPUT": "ptt"}).ptt is True
    assert load_config({"VOICE_INPUT": "fixed"}).input_mode == "fixed"
    assert load_config({"VOICE_INPUT": "fixed"}).ptt is False
    assert load_config({"VOICE_INPUT": "AUTO"}).input_mode == "auto"
    assert load_config({"VOICE_INPUT": " auto "}).input_mode == "auto"


def test_input_mode_invalid_raises():
    with pytest.raises(ValueError) as exc:
        load_config({"VOICE_INPUT": "nope"})
    assert "VOICE_INPUT" in str(exc.value)
    assert "nope" in str(exc.value)


def test_legacy_voice_ptt_maps_to_input_mode():
    for truthy in ("1", "true", "TRUE", "yes", "on", " On "):
        assert load_config({"VOICE_PTT": truthy}).input_mode == "ptt"
        assert load_config({"VOICE_PTT": truthy}).ptt is True
    for falsy in ("0", "false", "FALSE", "no", "off", "", "2", "sim"):
        assert load_config({"VOICE_PTT": falsy}).input_mode == "fixed"
        assert load_config({"VOICE_PTT": falsy}).ptt is False


def test_voice_input_wins_over_legacy_ptt():
    cfg = load_config({"VOICE_PTT": "1", "VOICE_INPUT": "auto"})
    assert cfg.input_mode == "auto"
    assert cfg.ptt is False


def test_serve_port_helper():
    from config import serve_port
    assert serve_port("http://127.0.0.1:4096") == 4096
    assert serve_port("http://127.0.0.1:9999") == 9999
    assert serve_port("http://127.0.0.1") == 4096
    assert serve_port("http://127.0.0.1:notaport") == 4096


def test_state_defaults():
    from config import DEFAULT_STATE_PORT
    cfg = load_config({})
    assert cfg.state_port == DEFAULT_STATE_PORT == 8765
    assert cfg.state_require_gui is False


def test_state_env_overrides():
    cfg = load_config({"JARVIS_STATE_PORT": "9000", "JARVIS_REQUIRE_GUI": "1"})
    assert cfg.state_port == 9000
    assert cfg.state_require_gui is True
    for truthy in ("1", "true", "TRUE", "yes", "on"):
        assert load_config({"JARVIS_REQUIRE_GUI": truthy}).state_require_gui is True
    for falsy in ("0", "false", "no", "off", ""):
        assert load_config({"JARVIS_REQUIRE_GUI": falsy}).state_require_gui is False


def test_state_port_invalid_raises():
    with pytest.raises(ValueError) as exc:
        load_config({"JARVIS_STATE_PORT": "abc"})
    assert "JARVIS_STATE_PORT" in str(exc.value)


def test_stream_defaults():
    from config import (DEFAULT_STREAM_IDLE_MS, DEFAULT_STREAM_MIN_CHARS,
                        DEFAULT_STREAM_TTS)
    cfg = load_config({})
    assert cfg.stream_tts is True
    assert cfg.stream_idle_ms == DEFAULT_STREAM_IDLE_MS == 400
    assert cfg.stream_min_chars == DEFAULT_STREAM_MIN_CHARS == 15
    assert DEFAULT_STREAM_TTS is True


def test_stream_env_overrides():
    cfg = load_config({
        "VOICE_STREAM_TTS": "0",
        "VOICE_STREAM_IDLE_MS": "250",
        "VOICE_STREAM_MIN_CHARS": "30",
    })
    assert cfg.stream_tts is False
    assert cfg.stream_idle_ms == 250
    assert cfg.stream_min_chars == 30


def test_stream_invalid_ints_raise():
    with pytest.raises(ValueError) as exc:
        load_config({"VOICE_STREAM_IDLE_MS": "abc"})
    assert "VOICE_STREAM_IDLE_MS" in str(exc.value)
    with pytest.raises(ValueError) as exc:
        load_config({"VOICE_STREAM_MIN_CHARS": "x"})
    assert "VOICE_STREAM_MIN_CHARS" in str(exc.value)


def test_capture_tunables_defaults():
    cfg = load_config({})
    assert cfg.noise_db == -35
    assert cfg.silence_s == 1.0
    assert cfg.wait_s == 8.0
    assert cfg.max_s == 15.0


def test_capture_tunables_env_overrides():
    cfg = load_config({
        "VOICE_NOISE_DB": "-45",
        "VOICE_SILENCE_S": "1.5",
        "VOICE_WAIT_S": "10",
        "VOICE_MAX_S": "20",
    })
    assert cfg.noise_db == -45
    assert cfg.silence_s == 1.5
    assert cfg.wait_s == 10.0
    assert cfg.max_s == 20.0


def test_capture_tunables_invalid_raise():
    with pytest.raises(ValueError) as exc:
        load_config({"VOICE_NOISE_DB": "x"})
    assert "VOICE_NOISE_DB" in str(exc.value)
    with pytest.raises(ValueError) as exc:
        load_config({"VOICE_SILENCE_S": "x"})
    assert "VOICE_SILENCE_S" in str(exc.value)
