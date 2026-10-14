"""Audio device selection and ownership of native temporary WAV files."""
import json
import os
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path


def input_args(cfg) -> list[str]:
    device = f'audio={cfg.mic_device}' if cfg.audio_backend == 'dshow' else cfg.mic_device
    return ['-f', cfg.audio_backend, '-i', device]


def new_audio_path(cfg) -> str:
    directory = Path(cfg.piper_out_wav).parent
    directory.mkdir(parents=True, exist_ok=True)
    fd, path = tempfile.mkstemp(prefix='jarvis-', suffix='.wav', dir=directory)
    os.close(fd)
    return path


@contextmanager
def temporary_audio(cfg):
    path = new_audio_path(cfg)
    try:
        yield path
    finally:
        Path(path).unlink(missing_ok=True)


def list_devices(cfg) -> list[str]:
    from tts import VoiceError
    if cfg.audio_backend == 'pulse':
        cmd = ['pactl', '--format=json', 'list', 'sources']
    elif cfg.audio_backend == 'alsa':
        cmd = ['arecord', '-L']
    else:
        raise VoiceError('list_devices Linux exige pulse ou alsa')
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, errors='replace', timeout=15)
        if result.returncode:
            raise VoiceError(f'falha ao listar microfones: {result.stderr.strip()[-200:]}')
        if cfg.audio_backend == 'pulse':
            data = json.loads(result.stdout)
            names = [item['name'] for item in data if not item['name'].endswith('.monitor')]
        else:
            names = [line.strip() for line in result.stdout.splitlines() if line and not line[0].isspace()]
        return list(dict.fromkeys(['default', *names]))
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError) as exc:
        raise VoiceError(f'falha ao listar microfones ({cmd[0]}): {exc}') from exc


@contextmanager
def recording_output(cfg, requested: str | None, legacy_default: str):
    """A successful capture belongs to its caller; failed implicit files do not."""
    owned = cfg.platform == 'linux' and requested is None
    output = new_audio_path(cfg) if owned else (requested or legacy_default)
    try:
        yield output
    except BaseException:
        if owned:
            Path(output).unlink(missing_ok=True)
        raise
