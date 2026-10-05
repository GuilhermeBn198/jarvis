import queue
import re
import subprocess
import threading
import time

from config import Config, load_config, win_path
from paths import _windows_to_wsl, _wsl_to_windows
from tts import VoiceError

# Defaults consistentes: ffmpeg e o microfone sao do Windows (dshow),
# entao ambos os modos gravam num diretorio visivel ao Windows.
DEFAULT_OUT_WAV = _wsl_to_windows(win_path("tools/jarvis_rec.wav"))
DEFAULT_AUTO_OUT_WAV = _wsl_to_windows(win_path("tools/jarvis_rec_auto.wav"))

# Limiar (s) abaixo do qual um silence_start e considerado a pausa
# inicial da captura, e nao o fim de uma fala.
EPS = 0.3


class QuitRequested(Exception):
    """Pedido de encerramento (comando `quit`) detectado durante a gravacao."""


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


def _parse_silence_end(line: str) -> float | None:
    try:
        tail = line.split("silence_end:", 1)[1]
        return float(tail.strip().split()[0])
    except (IndexError, ValueError):
        return None


def record_auto(out_path: str | None = None, config: Config | None = None,
                max_s: float | None = None, wait_s: float | None = None,
                silence_s: float | None = None, noise_db: int | None = None,
                min_speech_s: float | None = None, should_stop=None,
                on_level=None, eps: float = EPS) -> str:
    cfg = config or load_config()
    out = out_path or DEFAULT_AUTO_OUT_WAV
    # Sem parametro explicito, usa os tunables do config (env VOICE_*).
    if max_s is None:
        max_s = cfg.max_s
    if wait_s is None:
        wait_s = cfg.wait_s
    if silence_s is None:
        silence_s = cfg.silence_s
    if noise_db is None:
        noise_db = cfg.noise_db
    if min_speech_s is None:
        min_speech_s = cfg.min_speech_s
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
    speech_start: float | None = None
    t0 = time.monotonic()
    try:
        while True:
            if should_stop is not None and should_stop():
                # Encerramento pedido (ex.: botao Sair): nao espera o max_s.
                raise QuitRequested()
            if time.monotonic() - t0 > max_s:
                if heard_speech:
                    _stop(wait=True)
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
                # Fim de um silencio = inicio de som. Guarda o instante para
                # medir a duracao do segmento nao-silencioso.
                t = _parse_silence_end(line)
                speech_start = t if t is not None else 0.0
                heard_speech = True
                if on_level is not None:
                    on_level(1.0)
            elif "silence_start" in line:
                if on_level is not None:
                    on_level(0.0)
                t = _parse_silence_start(line)
                if t is None:
                    continue
                if speech_start is not None:
                    # Duracao da fala = inicio do som -> inicio do silencio.
                    if (t - speech_start) >= min_speech_s:
                        _stop(wait=True)
                        break
                    # Segmento curto demais: provavel ruido; volta a esperar.
                    speech_start = None
                    heard_speech = False
                elif t > eps:
                    # Audio nao-silencioso desde o inicio ate t: houve fala
                    # imediata (sem leading silence, sem silence_end).
                    if t >= min_speech_s:
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


def _first_float(line: str):
    for tok in line.replace(":", " ").split():
        try:
            return float(tok)
        except ValueError:
            continue
    return None


def parse_volume(stderr: str) -> dict:
    """Extrai `mean_volume`/`max_volume` (dBFS) da saida do `volumedetect`."""
    out: dict = {"mean_db": None, "max_db": None}
    for line in (stderr or "").splitlines():
        if "mean_volume:" in line:
            out["mean_db"] = _first_float(line)
        elif "max_volume:" in line:
            out["max_db"] = _first_float(line)
    return out


def measure_level(seconds: float = 5, config: Config | None = None) -> dict:
    """Mede o nivel do microfone (dBFS) por `seconds` via ffmpeg volumedetect.

    Use para calibrar `VOICE_NOISE_DB`: em silencio, o `mean_db` e o ruido de
    fundo; um bom limiar fica ~6-10 dB acima dele.
    """
    cfg = config or load_config()
    cmd = [
        cfg.ffmpeg_exe, "-f", "dshow", "-i", f"audio={cfg.mic_device}",
        "-t", str(seconds), "-af", "volumedetect", "-f", "null", "-",
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, errors="replace",
            timeout=int(seconds) + 30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise VoiceError(
            f"falha ao medir o microfone (FFMPEG_EXE={cfg.ffmpeg_exe}): {exc}"
        ) from exc
    if proc.returncode != 0:
        raise VoiceError(
            f"ffmpeg falhou ({proc.returncode}): {proc.stderr.strip()[-200:]}"
        )
    return parse_volume(proc.stderr)


_DEVICE_RE = re.compile(r'"([^"]+)"\s*\(([^)]*)\)')


def parse_audio_devices(stderr: str) -> list[str]:
    """Extrai os nomes dos devices de **audio** da saida do `-list_devices`.

    Linhas do ffmpeg: `[dshow @ x] "Microphone (FIFINE)" (audio)` e, para
    devices mistos, `"Webcam" (video, audio)`.
    """
    found: list[str] = []
    for line in (stderr or "").splitlines():
        match = _DEVICE_RE.search(line)
        if not match:
            continue
        name, kinds = match.group(1), match.group(2)
        if "audio" in kinds and name not in found:
            found.append(name)
    return found


def list_audio_devices(config: Config | None = None) -> list[str]:
    """Lista os microfones (dshow) do Windows sem abrir o device.

    `-i dummy` faz o ffmpeg falhar de proposito depois de enumerar; por isso o
    returncode e ignorado e so o stderr interessa.
    """
    cfg = config or load_config()
    cmd = [
        cfg.ffmpeg_exe, "-hide_banner", "-list_devices", "true",
        "-f", "dshow", "-i", "dummy",
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, errors="replace", timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise VoiceError(
            f"falha ao listar microfones (FFMPEG_EXE={cfg.ffmpeg_exe}): {exc}"
        ) from exc
    return parse_audio_devices(proc.stderr)
