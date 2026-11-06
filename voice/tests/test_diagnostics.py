import json
import importlib.util
import subprocess
import sys
from pathlib import Path
from config import load_config
from diagnostics import diagnose


def test_doctor_reports_missing_dependencies_without_side_effects(tmp_path, monkeypatch):
    monkeypatch.setenv('PATH', str(tmp_path))
    monkeypatch.delenv('DISPLAY', raising=False)
    monkeypatch.delenv('WAYLAND_DISPLAY', raising=False)
    monkeypatch.delenv('XDG_SESSION_TYPE', raising=False)
    cfg = load_config({'JARVIS_PLATFORM': 'linux', 'PIPER_MODEL': str(tmp_path / 'missing.onnx')})
    report = diagnose(cfg)
    assert report['platform'] == 'linux'
    assert report['session'] == 'headless'
    assert report['dependencies']['ffmpeg']['available'] is False
    assert report['dependencies']['piper_model']['available'] is False
    assert report['capabilities']['capture']['available'] is False
    assert list(tmp_path.iterdir()) == []


def test_doctor_marks_pulse_capture_unavailable_when_server_is_unreachable(monkeypatch):
    cfg = load_config({'JARVIS_PLATFORM': 'linux', 'AUDIO_BACKEND': 'pulse'})
    monkeypatch.setattr('diagnostics.shutil.which', lambda executable: f'/usr/bin/{executable}')
    def run(argv, **kwargs):
        if argv == ['ffmpeg', '-hide_banner', '-demuxers']:
            return subprocess.CompletedProcess(argv, 0, '', ' D d pulse Pulse audio input\n')
        assert argv == ['ffmpeg', '-hide_banner', '-sources', 'pulse']
        return subprocess.CompletedProcess(argv, 0, '', 'Auto-detected sources for pulse:\nCannot list sources: Connection refused')
    monkeypatch.setattr('audio.subprocess.run', run)

    capture = diagnose(cfg)['capabilities']['capture']

    assert capture['available'] is False
    assert 'Connection refused' in capture['reason']


def test_doctor_reports_pulse_server_reachable_without_claiming_capture_tested(monkeypatch):
    cfg = load_config({'JARVIS_PLATFORM': 'linux', 'AUDIO_BACKEND': 'pulse'})
    monkeypatch.setattr('diagnostics.shutil.which', lambda executable: f'/usr/bin/{executable}')
    def run(argv, **kwargs):
        if argv == ['ffmpeg', '-hide_banner', '-demuxers']:
            return subprocess.CompletedProcess(argv, 0, '', ' D d pulse Pulse audio input\n')
        assert argv == ['ffmpeg', '-hide_banner', '-sources', 'pulse']
        return subprocess.CompletedProcess(argv, 0, '', 'Auto-detected sources for pulse:\n  mic_usb [USB microphone] (input)\n')
    monkeypatch.setattr('audio.subprocess.run', run)

    capture = diagnose(cfg)['capabilities']['capture']

    assert capture['available'] is True
    assert capture['backend'] == 'pulse'
    assert 'gravacao real ainda nao testada' in capture['reason']
    assert 'ffmpeg enumera fontes' in capture['reason']


def test_doctor_marks_capture_unavailable_when_ffmpeg_lacks_backend_demuxer(monkeypatch):
    cfg = load_config({'JARVIS_PLATFORM': 'linux', 'AUDIO_BACKEND': 'pulse'})
    monkeypatch.setattr('diagnostics.shutil.which', lambda executable: f'/usr/bin/{executable}')
    def run(argv, **kwargs):
        if argv == ['ffmpeg', '-hide_banner', '-demuxers']:
            return subprocess.CompletedProcess(argv, 0, '', ' D d alsa ALSA audio input\n')
        raise AssertionError(f'no device scan should run without an FFmpeg demuxer: {argv}')
    monkeypatch.setattr('audio.subprocess.run', run)

    capture = diagnose(cfg)['capabilities']['capture']

    assert capture['available'] is False
    assert 'ffmpeg nao disponibiliza entrada pulse' in capture['reason']


def test_doctor_checks_alsa_input_support_without_requiring_arecord(monkeypatch):
    cfg = load_config({'JARVIS_PLATFORM': 'linux', 'AUDIO_BACKEND': 'alsa'})
    monkeypatch.setattr('diagnostics.shutil.which', lambda executable: f'/usr/bin/{executable}')
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        if argv == ['ffmpeg', '-hide_banner', '-demuxers']:
            return subprocess.CompletedProcess(argv, 0, '', ' D d alsa ALSA audio input\n')
        assert argv == ['ffmpeg', '-hide_banner', '-sources', 'alsa']
        return subprocess.CompletedProcess(argv, 0, '', 'Auto-detected sources for alsa:\n  default [Default PCM]\n')
    monkeypatch.setattr('audio.subprocess.run', run)

    capture = diagnose(cfg)['capabilities']['capture']

    assert capture['available'] is True
    assert capture['backend'] == 'alsa'
    assert 'gravacao real ainda nao testada' in capture['reason']
    assert 'ffmpeg enumera fontes' in capture['reason']
    assert calls == [['ffmpeg', '-hide_banner', '-demuxers'], ['ffmpeg', '-hide_banner', '-sources', 'alsa']]


def test_doctor_cli_prints_json_without_starting_agent():
    proc = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'loop.py'), '--doctor'], capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0
    assert json.loads(proc.stdout)['platform'] == 'linux'


def test_doctor_wayland_reports_authorization_requirement(monkeypatch):
    monkeypatch.setenv('WAYLAND_DISPLAY','wayland-test')
    monkeypatch.setattr(importlib.util, 'find_spec', lambda name: object() if name == 'dbus_next' else None)
    cfg=load_config({'JARVIS_PLATFORM':'linux'})
    desktop=diagnose(cfg)['capabilities']['desktop']
    assert desktop['backend']=='wayland'
    assert desktop['available'] is True
    assert desktop['validation']=='not_run'
    assert desktop['authorization_required'] is True
    assert desktop['eis_input_available'] is False
    assert 'fallback RemoteDesktop' in desktop['eis_input_reason']
    assert 'autorizacao' in desktop['reason']
    assert 'nao implementado' not in desktop['reason']


def test_doctor_reports_eis_when_python_and_native_libraries_are_available(monkeypatch):
    import sys
    from types import SimpleNamespace
    monkeypatch.setenv('WAYLAND_DISPLAY','wayland-test')
    monkeypatch.setattr(importlib.util, 'find_spec', lambda name: object() if name in ('dbus_next','libei') else None)
    monkeypatch.setitem(sys.modules,'libei',SimpleNamespace(
        ei=SimpleNamespace(is_available=lambda:True),
        portal=SimpleNamespace(is_available=lambda:True)))
    desktop=diagnose(load_config({'JARVIS_PLATFORM':'linux'}))['capabilities']['desktop']
    assert desktop['eis_input_available'] is True
    assert 'autorizacao do portal' in desktop['eis_input_reason']


def test_doctor_x11_reports_runtime_requirement(monkeypatch):
    monkeypatch.delenv('WAYLAND_DISPLAY',raising=False)
    monkeypatch.setenv('XDG_SESSION_TYPE','x11')
    monkeypatch.setenv('DISPLAY',':99')
    cfg=load_config({'JARVIS_PLATFORM':'linux'})
    desktop=diagnose(cfg)['capabilities']['desktop']
    assert desktop['validation']=='not_run'
    assert 'xdotool' in desktop['reason']
