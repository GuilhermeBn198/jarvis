import base64
import subprocess

from config import Config, load_config


class VoiceError(RuntimeError):
    pass


def _ps_script(text_b64: str, out_b64: str | None) -> str:
    out_line = (
        "if ('{}' -ne '') {{ $s.SetOutputToWaveFile("
        "[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{}'))) }}"
    ).format(out_b64, out_b64) if out_b64 else "if ($false) {}"
    return (
        "Add-Type -AssemblyName System.Speech; "
        f"$t=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{text_b64}')); "
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"{out_line}; "
        "$s.Speak($t); $s.Dispose()"
    )


def _encoded(script: str) -> str:
    return base64.b64encode(script.encode("utf-16-le")).decode("ascii")


def _to_windows_path(path: str) -> str:
    if path.startswith("/mnt/") and len(path) > 6 and path[5].isalpha() and path[6] == "/":
        rest = path[7:].replace("/", "\\")
        return f"{path[5].upper()}:\\{rest}"
    return path


def speak(text: str, to_file: str | None = None, config: Config | None = None) -> None:
    cfg = config or load_config()
    if cfg.tts_backend == "piper":
        return speak_piper(text, to_file=to_file, config=cfg)
    return speak_sapi(text, to_file=to_file, config=cfg)


def speak_sapi(text: str, to_file: str | None = None, config: Config | None = None) -> None:
    text = (text or "").strip()
    if not text:
        return
    cfg = config or load_config()
    b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    out_b64 = (
        base64.b64encode(to_file.encode("utf-8")).decode("ascii") if to_file else None
    )
    script = _ps_script(b64, out_b64)
    cmd = [cfg.powershell_exe, "-NoProfile", "-EncodedCommand", _encoded(script)]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, errors="replace", timeout=120
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise VoiceError(f"falha ao falar via SAPI: {exc}") from exc
    if proc.returncode != 0:
        raise VoiceError(f"SAPI falhou ({proc.returncode}): {proc.stderr.strip()[:200]}")


def speak_piper(text: str, to_file: str | None = None,
                config: Config | None = None) -> None:
    text = (text or "").strip()
    if not text:
        return
    cfg = config or load_config()
    out_windows = _to_windows_path(
        to_file if to_file is not None else cfg.piper_out_wav
    )
    model = _to_windows_path(cfg.piper_model)
    cmd = [cfg.piper_exe, "-m", model, "-f", out_windows]
    try:
        proc = subprocess.run(
            cmd, input=text, text=True, capture_output=True, timeout=60
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise VoiceError(f"falha ao sintetizar com piper: {exc}") from exc
    if proc.returncode != 0:
        raise VoiceError(
            f"piper falhou ({proc.returncode}): {proc.stderr.strip()[:200]}"
        )
    if to_file is None:
        play = [cfg.ffplay_exe, "-nodisp", "-autoexit", "-loglevel", "quiet",
                out_windows]
        try:
            proc = subprocess.run(
                play, capture_output=True, text=True, errors="replace", timeout=120
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise VoiceError(f"falha ao reproduzir com ffplay: {exc}") from exc
        if proc.returncode != 0:
            raise VoiceError(
                f"ffplay falhou ({proc.returncode}): {proc.stderr.strip()[:200]}"
            )
