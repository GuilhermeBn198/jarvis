import queue
import subprocess
import threading
import time

from config import Config, load_config
from tts import VoiceError
from vision import _windows_to_wsl, _wsl_to_windows

DEFAULT_AUTO_OUT_WAV = r"C:\Users\bguil\tools\jarvis_rec_auto.wav"


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


def record_auto(out_path: str | None = None, config: Config | None = None,
                max_s: float = 15, wait_s: float = 8.0, silence_s: float = 1.0,
                noise_db: int = -35) -> str:
    cfg = config or load_config()
    out = out_path or DEFAULT_AUTO_OUT_WAV
    cmd = [
        cfg.ffmpeg_exe, "-y", "-f", "dshow", "-i", f"audio={cfg.mic_device}",
        "-af", f"silencedetect=noise={noise_db}dB:d={silence_s}",
        "-t", str(max_s), "-nostats", "-loglevel", "info",
        _wsl_to_windows(out),
    ]
    try:
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, text=True, bufsize=1,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise VoiceError(
            f"falha ao gravar audio (FFMPEG_EXE={cfg.ffmpeg_exe}): {exc}"
        ) from exc

    lines: "queue.Queue[str | None]" = queue.Queue()

    def _reader() -> None:
        try:
            for line in proc.stderr:
                lines.put(line)
        except Exception:
            pass
        finally:
            lines.put(None)

    threading.Thread(target=_reader, daemon=True).start()

    heard_speech = False
    t0 = time.monotonic()
    try:
        while True:
            if time.monotonic() - t0 > max_s:
                if heard_speech:
                    proc.stdin.write("q")
                    proc.stdin.flush()
                break
            try:
                line = lines.get(timeout=0.2)
            except queue.Empty:
                if not heard_speech and time.monotonic() - t0 > wait_s:
                    break
                continue
            if line is None:
                break
            if "silence_end" in line:
                heard_speech = True
            elif "silence_start" in line and heard_speech:
                proc.stdin.write("q")
                proc.stdin.flush()
                proc.wait(timeout=20)
                break
            if not heard_speech and time.monotonic() - t0 > wait_s:
                break
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
    return _windows_to_wsl(out) if heard_speech else ""
