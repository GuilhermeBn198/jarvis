import subprocess

from agent_client import strip_opencode_noise
from config import Config, load_config
from paths import _windows_to_wsl, _wsl_to_windows
from tts import VoiceError


def capture(out_path: str | None = None, config: Config | None = None) -> str:
    cfg = config or load_config()
    win_path = _wsl_to_windows(out_path) if out_path else cfg.vision_png
    cmd = [
        cfg.ffmpeg_exe, "-y", "-f", "gdigrab", "-i", "desktop",
        "-frames:v", "1", "-update", "1", win_path,
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, errors="replace", timeout=60
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise VoiceError(f"falha ao capturar a tela (FFMPEG_EXE): {exc}") from exc
    if proc.returncode != 0:
        raise VoiceError(
            f"ffmpeg gdigrab falhou ({proc.returncode}): {proc.stderr.strip()[-200:]}"
        )
    return _windows_to_wsl(win_path)


def see(prompt: str, png_path: str, config: Config | None = None) -> str:
    cfg = config or load_config()
    prompt = (prompt or "").strip() or "Descreva o que esta na tela."
    cmd = [
        cfg.opencode_bin, "run", "--pure", prompt,
        "-m", cfg.vision_model, "-f", png_path,
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, errors="replace", timeout=cfg.timeout_s
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise VoiceError(f"falha na consulta de visao: {exc}") from exc
    if proc.returncode != 0:
        raise VoiceError(
            f"visao falhou ({proc.returncode}): {proc.stderr.strip()[:200]}"
        )
    cleaned = strip_opencode_noise(proc.stdout).strip()
    if not cleaned:
        raise VoiceError("visao nao retornou resposta")
    return cleaned
