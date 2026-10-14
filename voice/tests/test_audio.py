import subprocess
from pathlib import Path
import pytest
from config import load_config
from audio import input_args, list_devices, temporary_audio
from capture import record, measure_level
from tts import speak_piper


def linux(**env):
    return load_config({'JARVIS_PLATFORM': 'linux', **env})


def test_capture_args_native_and_wsl():
    assert input_args(linux()) == ['-f', 'pulse', '-i', 'default']
    assert input_args(linux(AUDIO_BACKEND='alsa', MIC_DEVICE='hw:1,0')) == ['-f', 'alsa', '-i', 'hw:1,0']
    assert input_args(load_config({'JARVIS_PLATFORM': 'wsl', 'MIC_DEVICE': 'Mic'})) == ['-f', 'dshow', '-i', 'audio=Mic']


def test_pulse_devices_keep_names_and_default(monkeypatch):
    def run(argv, **kwargs):
        assert argv == ['pactl', '--format=json', 'list', 'sources']
        return subprocess.CompletedProcess(argv, 0, '[{"name":"mic usb"},{"name":"speaker.monitor"}]', '')
    monkeypatch.setattr(subprocess, 'run', run)
    assert list_devices(linux()) == ['default', 'mic usb']


def test_temporary_audio_unique_and_cleaned(tmp_path):
    cfg = linux(XDG_CACHE_HOME=str(tmp_path))
    with temporary_audio(cfg) as first, temporary_audio(cfg) as second:
        assert first != second
        assert Path(first).is_file() and Path(second).is_file()
    assert not Path(first).exists() and not Path(second).exists()


def test_native_record_and_measure_argv(monkeypatch, tmp_path):
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, '', 'mean_volume: -42 dB\nmax_volume: -10 dB')
    monkeypatch.setattr(subprocess, 'run', run)
    path = str(tmp_path / 'áudio test.wav')
    assert record(1, path, linux()) == path
    assert calls[0][:5] == ['ffmpeg', '-f', 'pulse', '-i', 'default']
    assert calls[0][-1] == path
    assert measure_level(1, linux())['mean_db'] == -42
    assert calls[1][:5] == ['ffmpeg', '-f', 'pulse', '-i', 'default']


def test_piper_native_paths_and_cleanup(monkeypatch, tmp_path):
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, '', '')
    monkeypatch.setattr(subprocess, 'run', run)
    cfg = linux(XDG_CACHE_HOME=str(tmp_path), PIPER_MODEL='/mnt/c/local/model.onnx')
    speak_piper('Olá', config=cfg)
    assert calls[0][2] == '/mnt/c/local/model.onnx'
    wav = calls[0][-1]
    assert calls[1][-1] == wav
    assert not Path(wav).exists()


def test_alsa_list_and_server_failure(monkeypatch):
    def run(argv, **kwargs):
        assert argv == ['arecord', '-L']
        return subprocess.CompletedProcess(argv, 0, 'default\n    Default PCM\nhw:CARD=PCH,DEV=0\n    hardware\n', '')
    monkeypatch.setattr(subprocess, 'run', run)
    assert list_devices(linux(AUDIO_BACKEND='alsa')) == ['default', 'hw:CARD=PCH,DEV=0']
    from tts import VoiceError
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess(a[0], 1, '', 'Connection refused'))
    with pytest.raises(VoiceError, match='Connection refused'):
        list_devices(linux())


def test_piper_failure_removes_owned_wav(monkeypatch, tmp_path):
    from tts import VoiceError
    cfg = linux(XDG_CACHE_HOME=str(tmp_path))
    monkeypatch.setattr(subprocess, 'run', lambda argv, **kw: subprocess.CompletedProcess(argv, 1, '', 'model missing'))
    with pytest.raises(VoiceError, match='model missing'):
        speak_piper('Olá', config=cfg)
    assert list((tmp_path / 'jarvis').glob('*.wav')) == []


def test_missing_device_surfaces_error(monkeypatch, tmp_path):
    from tts import VoiceError
    monkeypatch.setattr(subprocess, 'run', lambda argv, **kw: subprocess.CompletedProcess(argv, 1, '', 'No such device'))
    with pytest.raises(VoiceError, match='No such device'):
        record(1, str(tmp_path / 'requested.wav'), linux(MIC_DEVICE='missing'))


def test_failed_implicit_recording_does_not_leak(monkeypatch, tmp_path):
    from tts import VoiceError
    cfg = linux(XDG_CACHE_HOME=str(tmp_path))
    monkeypatch.setattr(subprocess, 'run', lambda argv, **kw: subprocess.CompletedProcess(argv, 1, '', 'No such device'))
    with pytest.raises(VoiceError):
        record(1, config=cfg)
    assert list((tmp_path / 'jarvis').glob('*.wav')) == []


def test_auto_capture_device_error_is_not_silence(monkeypatch, tmp_path):
    import io
    from capture import record_auto
    from tts import VoiceError
    class FailedCapture:
        returncode = 1
        stdin = io.StringIO()
        stderr = io.StringIO('No such device\n')
        def poll(self):
            return 1
    monkeypatch.setattr(subprocess, 'Popen', lambda *a, **kw: FailedCapture())
    with pytest.raises(VoiceError, match='ffmpeg falhou'):
        record_auto(config=linux(XDG_CACHE_HOME=str(tmp_path)))
    assert list((tmp_path / 'jarvis').glob('*.wav')) == []
