import subprocess

from agent_client import AgentError, ServeClient, strip_opencode_noise
from config import Config, load_config
from paths import _windows_to_wsl, _wsl_to_windows
from serve import ensure_server
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


def _see_via_run(cfg: Config, prompt: str, png_path: str) -> str:
    """Fallback de visao via `opencode run` (startup caro: ~29s).

    NAO usar --pure e usar o agente TOOL-LESS `chat`.
    """
    cmd = [
        cfg.opencode_bin, "run", "--agent", "chat", prompt,
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


def see(prompt: str, png_path: str, config: Config | None = None) -> str:
    cfg = config or load_config()
    prompt = (prompt or "").strip() or "Descreva o que esta na tela."
    # Via de regra usamos o `serve` (session ja aquecida): o startup do
    # `opencode run` domina a latencia de visao (~29s run vs ~6.5s serve).
    # O agente continua sendo o TOOL-LESS `chat`: o conteudo da tela e
    # nao-conflavel e nao pode rodar tools/plugins (SafetyGate, act_*).
    if ensure_server(cfg):
        try:
            return ServeClient(cfg).see(prompt, png_path, model_id=cfg.vision_model)
        except AgentError as exc:
            raise VoiceError(f"visao falhou: {exc}") from exc
    # Fallback: servidor indisponivel -> `opencode run`.
    return _see_via_run(cfg, prompt, png_path)
