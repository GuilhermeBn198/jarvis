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


def speak(text: str, to_file: str | None = None, config: Config | None = None) -> None:
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
