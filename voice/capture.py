import subprocess

from config import Config, load_config
from tts import VoiceError


def record(seconds: float, out_path: str | None = None, config: Config | None = None) -> str:
    cfg = config or load_config()
    out = out_path or "/tmp/jarvis_rec.wav"
    cmd = [cfg.ffmpeg_exe, "-f", "dshow", "-i", f"audio={cfg.mic_device}",
           "-t", str(seconds), "-y", out]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=int(seconds) + 30)
    except (OSError, subprocess.SubprocessError) as exc:
        raise VoiceError(f"falha ao gravar audio: {exc}") from exc
    if proc.returncode != 0:
        raise VoiceError(f"ffmpeg falhou ({proc.returncode}): {proc.stderr.strip()[-200:]}")
    return out
