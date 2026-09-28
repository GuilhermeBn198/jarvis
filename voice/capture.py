import subprocess

from config import Config, load_config
from tts import VoiceError


def record(seconds: float, out_path: str | None = None, config: Config | None = None) -> str:
    cfg = config or load_config()
    out = out_path or "/tmp/jarvis_rec.wav"
    cmd = [cfg.ffmpeg_exe, "-f", "dshow", "-i", f"audio={cfg.mic_device}",
           "-t", str(seconds), "-y", out]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, errors="replace",
            timeout=int(seconds) + 30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise VoiceError(
            f"falha ao gravar audio (FFMPEG_EXE={cfg.ffmpeg_exe}): {exc}"
        ) from exc
    if proc.returncode != 0:
        raise VoiceError(f"ffmpeg falhou ({proc.returncode}): {proc.stderr.strip()[-200:]}")
    return out


def record_ptt(out_path: str | None = None, config: Config | None = None,
               prompt_fn=input) -> str:
    cfg = config or load_config()
    out = out_path or "/tmp/jarvis_rec.wav"
    cmd = [cfg.ffmpeg_exe, "-y", "-f", "dshow", "-i",
           f"audio={cfg.mic_device}", out]
    prompt_fn("Pressione Enter para comecar a gravar...")
    try:
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise VoiceError(
            f"falha ao gravar audio (FFMPEG_EXE={cfg.ffmpeg_exe}): {exc}"
        ) from exc
    try:
        prompt_fn("Fale agora. Pressione Enter para parar...")
        proc.stdin.write(b"q")
        proc.stdin.flush()
        proc.wait(timeout=20)
    except (OSError, subprocess.SubprocessError) as exc:
        raise VoiceError(
            f"falha ao gravar audio (FFMPEG_EXE={cfg.ffmpeg_exe}): {exc}"
        ) from exc
    finally:
        if proc.poll() is None:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except Exception:
                pass
    if proc.returncode != 0:
        raise VoiceError(f"ffmpeg falhou ({proc.returncode})")
    return out
