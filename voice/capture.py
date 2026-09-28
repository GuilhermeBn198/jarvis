import queue
import subprocess
import threading
import time

from config import Config, load_config
from paths import _windows_to_wsl, _wsl_to_windows
from tts import VoiceError

# Defaults consistentes: ffmpeg e o microfone sao do Windows (dshow),
# entao ambos os modos gravam num diretorio visivel ao Windows.
DEFAULT_OUT_WAV = r"C:\Users\bguil\tools\jarvis_rec.wav"
DEFAULT_AUTO_OUT_WAV = r"C:\Users\bguil\tools\jarvis_rec_auto.wav"

# Limiar (s) abaixo do qual um silence_start e considerado a pausa
# inicial da captura, e nao o fim de uma fala.
EPS = 0.3


def record(seconds: float, out_path: str | None = None, config: Config | None = None) -> str:
    cfg = config or load_config()
    out = out_path or DEFAULT_OUT_WAV
    cmd = [cfg.ffmpeg_exe, "-f", "dshow", "-i", f"audio={cfg.mic_device}",
           "-t", str(seconds), "-y", _wsl_to_windows(out)]
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
    return _windows_to_wsl(out)


def record_ptt(out_path: str | None = None, config: Config | None = None,
               prompt_fn=input) -> str:
    cfg = config or load_config()
    out = out_path or DEFAULT_OUT_WAV
    cmd = [cfg.ffmpeg_exe, "-y", "-f", "dshow", "-i",
           f"audio={cfg.mic_device}", _wsl_to_windows(out)]
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
    return _windows_to_wsl(out)


def _parse_silence_start(line: str) -> float | None:
    try:
        tail = line.split("silence_start:", 1)[1]
        return float(tail.strip().split()[0])
    except (IndexError, ValueError):
        return None


def record_auto(out_path: str | None = None, config: Config | None = None,
                max_s: float = 15, wait_s: float = 8.0, silence_s: float = 1.0,
                noise_db: int = -35, eps: float = EPS) -> str:
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

    def _stop(wait: bool) -> None:
        try:
            proc.stdin.write("q")
            proc.stdin.flush()
            if wait:
                proc.wait(timeout=20)
        except (OSError, subprocess.SubprocessError):
            pass

    heard_speech = False
    t0 = time.monotonic()
    try:
        while True:
            if time.monotonic() - t0 > max_s:
                if heard_speech:
                    _stop(wait=False)
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
            elif "silence_start" in line:
                t = _parse_silence_start(line)
                if heard_speech:
                    # Fala terminou (silencio apos inicio conhecido).
                    _stop(wait=True)
                    break
                if t is not None and t > eps:
                    # Audio nao-silencioso desde o inicio ate t: houve fala
                    # imediata (sem leading silence, sem silence_end).
                    heard_speech = True
                    _stop(wait=True)
                    break
                # t <= eps: pausa inicial; continua aguardando.
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
