from pathlib import Path
import pytest
from platforms import detect_platform, desktop_session, xdg_path
from config import load_config


def test_native_linux_defaults_and_override():
    cfg = load_config({'JARVIS_PLATFORM': 'linux', 'HOME': '/home/test'})
    assert (cfg.platform, cfg.audio_backend, cfg.ffmpeg_exe, cfg.ffplay_exe,
            cfg.piper_exe, cfg.mic_device) == ('linux', 'pulse', 'ffmpeg', 'ffplay', 'piper', 'default')
    assert cfg.piper_model == '/home/test/.local/share/jarvis/voices/pt_BR-faber-medium.onnx'
    assert load_config({'JARVIS_PLATFORM': 'linux', 'FFMPEG_EXE': '/custom ffmpeg'}).ffmpeg_exe == '/custom ffmpeg'


def test_wsl_detected_and_overridable():
    assert detect_platform({}, 'Linux microsoft-standard-WSL2') == 'wsl'
    assert detect_platform({'JARVIS_PLATFORM': 'linux'}, 'microsoft') == 'linux'
    assert detect_platform({}, 'Linux generic') == 'linux'
    with pytest.raises(ValueError, match='JARVIS_PLATFORM'):
        detect_platform({'JARVIS_PLATFORM': 'invalid'}, '')


def test_wayland_wins_over_xwayland():
    assert desktop_session({'XDG_SESSION_TYPE': 'wayland', 'DISPLAY': ':0'}) == 'wayland'
    assert desktop_session({'WAYLAND_DISPLAY': 'wayland-0', 'DISPLAY': ':0'}) == 'wayland'
    assert desktop_session({'DISPLAY': ':0'}) == 'x11'
    assert desktop_session({}) == 'headless'


def test_xdg_paths_preserve_unicode_and_ignore_relative():
    assert xdg_path('data', {'HOME': '/home/test', 'XDG_DATA_HOME': '/tmp/meus dados/ação'}) == Path('/tmp/meus dados/ação/jarvis')
    assert xdg_path('config', {'HOME': '/home/test', 'XDG_CONFIG_HOME': 'relative'}) == Path('/home/test/.config/jarvis')


def test_backend_platform_validation():
    with pytest.raises(ValueError, match='SAPI'):
        load_config({'JARVIS_PLATFORM': 'linux', 'TTS_BACKEND': 'sapi'})
    with pytest.raises(ValueError, match='AUDIO_BACKEND'):
        load_config({'JARVIS_PLATFORM': 'linux', 'AUDIO_BACKEND': 'dshow'})
    assert load_config({'JARVIS_PLATFORM': 'wsl'}).audio_backend == 'dshow'
    assert load_config({'JARVIS_PLATFORM': 'linux', 'AUDIO_BACKEND': 'alsa'}).audio_backend == 'alsa'


def test_native_agent_resolves_packaged_path_before_legacy_default(tmp_path):
    executable=tmp_path/'opencode'
    executable.write_text('#!/bin/sh\nexit 0\n');executable.chmod(0o755)
    cfg=load_config({'JARVIS_PLATFORM':'linux','PATH':str(tmp_path)})
    assert cfg.opencode_bin==str(executable)
    cfg=load_config({'JARVIS_PLATFORM':'linux','PATH':str(tmp_path),'OPENCODE_BIN':'/custom/opencode'})
    assert cfg.opencode_bin=='/custom/opencode'
