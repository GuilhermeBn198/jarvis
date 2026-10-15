import json
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


def test_doctor_cli_prints_json_without_starting_agent():
    proc = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'loop.py'), '--doctor'], capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0
    assert json.loads(proc.stdout)['platform'] == 'linux'


def test_doctor_wayland_reports_authorization_requirement(monkeypatch):
    monkeypatch.setenv('WAYLAND_DISPLAY','wayland-test')
    cfg=load_config({'JARVIS_PLATFORM':'linux'})
    desktop=diagnose(cfg)['capabilities']['desktop']
    assert desktop['backend']=='wayland'
    assert desktop['validation']=='not_run'
    assert 'autorizacao' in desktop['reason']
    assert 'nao implementado' not in desktop['reason']


def test_doctor_x11_reports_runtime_requirement(monkeypatch):
    monkeypatch.delenv('WAYLAND_DISPLAY',raising=False)
    monkeypatch.setenv('XDG_SESSION_TYPE','x11')
    monkeypatch.setenv('DISPLAY',':99')
    cfg=load_config({'JARVIS_PLATFORM':'linux'})
    desktop=diagnose(cfg)['capabilities']['desktop']
    assert desktop['validation']=='not_run'
    assert 'xdotool' in desktop['reason']
