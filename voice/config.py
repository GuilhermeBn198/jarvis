import os
from dataclasses import dataclass
from urllib.parse import urlparse

from settings import load_settings

DEFAULT_OPENCODE_BIN = os.path.expanduser("~/.opencode/bin/opencode")
DEFAULT_TIMEOUT_S = 300
DEFAULT_POWERSHELL_EXE = "powershell.exe"
DEFAULT_FFMPEG_EXE = (
    "/mnt/c/Users/bguil/tools/ffmpeg/ffmpeg-master-latest-win64-gpl/bin/ffmpeg.exe"
)
DEFAULT_MIC_DEVICE = "Microphone (FIFINE Microphone)"
DEFAULT_WHISPER_MODEL = "base"
DEFAULT_RECORD_SECONDS = 5
DEFAULT_INPUT_MODE = "auto"
INPUT_MODES = ("auto", "ptt", "fixed")
DEFAULT_LANGUAGE = "pt"
DEFAULT_AGENT_BACKEND = "serve"
DEFAULT_SERVER_URL = "http://127.0.0.1:4096"
DEFAULT_TTS_BACKEND = "piper"
DEFAULT_AGENT = "chat"
DEFAULT_VOICE_LOG = os.path.expanduser("~/.local/share/jarvis/voice-log.jsonl")
DEFAULT_PIPER_EXE = "/mnt/c/Users/bguil/tools/piper/piper/piper.exe"
DEFAULT_PIPER_MODEL = "/mnt/c/Users/bguil/tools/piper/voices/pt_BR-faber-medium.onnx"
DEFAULT_FFPLAY_EXE = (
    "/mnt/c/Users/bguil/tools/ffmpeg/ffmpeg-master-latest-win64-gpl/bin/ffplay.exe"
)
DEFAULT_PIPER_OUT_WAV = r"C:\Users\bguil\tools\piper\out.wav"
DEFAULT_VISION_MODEL = "opencode-go/deepseek-v4-flash-vision-exp"
DEFAULT_VISION_TRIGGER = "olha"
DEFAULT_VISION_PNG = r"C:\Users\bguil\tools\shot.png"
DEFAULT_STATE_PORT = 8765
DEFAULT_STATE_REQUIRE_GUI = False
DEFAULT_STREAM_TTS = True
DEFAULT_STREAM_IDLE_MS = 400
DEFAULT_STREAM_MIN_CHARS = 15
DEFAULT_NOISE_DB = -35
DEFAULT_SILENCE_S = 1.0
DEFAULT_WAIT_S = 8.0
DEFAULT_MAX_S = 15.0
DEFAULT_MIN_SPEECH_S = 0.4


@dataclass(frozen=True)
class Config:
    opencode_bin: str
    timeout_s: int
    powershell_exe: str = DEFAULT_POWERSHELL_EXE
    ffmpeg_exe: str = DEFAULT_FFMPEG_EXE
    mic_device: str = DEFAULT_MIC_DEVICE
    whisper_model: str = DEFAULT_WHISPER_MODEL
    record_seconds: int = DEFAULT_RECORD_SECONDS
    language: str = DEFAULT_LANGUAGE
    agent_backend: str = DEFAULT_AGENT_BACKEND
    agent: str | None = DEFAULT_AGENT
    server_url: str = DEFAULT_SERVER_URL
    tts_backend: str = DEFAULT_TTS_BACKEND
    voice_log_path: str = DEFAULT_VOICE_LOG
    piper_exe: str = DEFAULT_PIPER_EXE
    piper_model: str = DEFAULT_PIPER_MODEL
    ffplay_exe: str = DEFAULT_FFPLAY_EXE
    piper_out_wav: str = DEFAULT_PIPER_OUT_WAV
    vision_model: str = DEFAULT_VISION_MODEL
    vision_trigger: str = DEFAULT_VISION_TRIGGER
    vision_png: str = DEFAULT_VISION_PNG
    input_mode: str = DEFAULT_INPUT_MODE
    ptt: bool = False
    state_port: int = DEFAULT_STATE_PORT
    state_require_gui: bool = DEFAULT_STATE_REQUIRE_GUI
    stream_tts: bool = DEFAULT_STREAM_TTS
    stream_idle_ms: int = DEFAULT_STREAM_IDLE_MS
    stream_min_chars: int = DEFAULT_STREAM_MIN_CHARS
    noise_db: int = DEFAULT_NOISE_DB
    silence_s: float = DEFAULT_SILENCE_S
    wait_s: float = DEFAULT_WAIT_S
    max_s: float = DEFAULT_MAX_S
    min_speech_s: float = DEFAULT_MIN_SPEECH_S


def serve_port(server_url: str, default: int = 4096) -> int:
    try:
        return urlparse(server_url).port or default
    except ValueError:
        return default


def load_config(env: dict | None = None, settings: dict | None = None) -> Config:
    e = os.environ if env is None else env
    if settings is None:
        # Runtime (env real): o arquivo de settings entra como default; as
        # variaveis de ambiente tem precedencia. Testes passam um env dict e
        # ficam herméticos (settings vazio).
        settings = load_settings() if env is None else {}
    raw_timeout = e.get("VOICE_TIMEOUT_S", DEFAULT_TIMEOUT_S)
    try:
        timeout_s = int(raw_timeout)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"VOICE_TIMEOUT_S deve ser inteiro: {raw_timeout}") from exc
    raw_seconds = e.get("RECORD_SECONDS", DEFAULT_RECORD_SECONDS)
    try:
        record_seconds = int(raw_seconds)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"RECORD_SECONDS deve ser inteiro: {raw_seconds}") from exc
    agent_backend = e.get("AGENT_BACKEND", DEFAULT_AGENT_BACKEND)
    if agent_backend not in ("run", "serve"):
        raise ValueError(
            f"AGENT_BACKEND deve ser 'run' ou 'serve': {agent_backend}"
        )
    tts_backend = e.get("TTS_BACKEND", DEFAULT_TTS_BACKEND)
    if tts_backend not in ("sapi", "piper"):
        raise ValueError(
            f"TTS_BACKEND deve ser 'sapi' ou 'piper': {tts_backend}"
        )
    legacy_ptt = str(e.get("VOICE_PTT", "1")).strip().lower() in (
        "1", "true", "yes", "on",
    )
    raw_input = e.get("VOICE_INPUT")
    if raw_input is None:
        if "VOICE_PTT" in e:
            input_mode = "ptt" if legacy_ptt else "fixed"
        else:
            input_mode = DEFAULT_INPUT_MODE
    else:
        input_mode = str(raw_input).strip().lower()
        if input_mode not in INPUT_MODES:
            raise ValueError(
                f"VOICE_INPUT deve ser 'auto', 'ptt' ou 'fixed': {raw_input}"
            )
    ptt = input_mode == "ptt"
    raw_state_port = e.get("JARVIS_STATE_PORT", DEFAULT_STATE_PORT)
    try:
        state_port = int(raw_state_port)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"JARVIS_STATE_PORT deve ser inteiro: {raw_state_port}") from exc
    state_require_gui = str(
        e.get("JARVIS_REQUIRE_GUI", "0")
    ).strip().lower() in ("1", "true", "yes", "on")
    stream_tts = str(
        e.get("VOICE_STREAM_TTS", settings.get("stream_tts", "1"))
    ).strip().lower() in (
        "1", "true", "yes", "on",
    )
    raw_idle = e.get("VOICE_STREAM_IDLE_MS", DEFAULT_STREAM_IDLE_MS)
    try:
        stream_idle_ms = int(raw_idle)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"VOICE_STREAM_IDLE_MS deve ser inteiro: {raw_idle}") from exc
    raw_min = e.get("VOICE_STREAM_MIN_CHARS", DEFAULT_STREAM_MIN_CHARS)
    try:
        stream_min_chars = int(raw_min)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"VOICE_STREAM_MIN_CHARS deve ser inteiro: {raw_min}"
        ) from exc
    raw_noise = e.get("VOICE_NOISE_DB", settings.get("noise_db", DEFAULT_NOISE_DB))
    try:
        noise_db = int(raw_noise)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"VOICE_NOISE_DB deve ser inteiro: {raw_noise}") from exc
    raw_silence = e.get("VOICE_SILENCE_S", settings.get("silence_s", DEFAULT_SILENCE_S))
    try:
        silence_s = float(raw_silence)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"VOICE_SILENCE_S deve ser numero: {raw_silence}") from exc
    raw_wait = e.get("VOICE_WAIT_S", settings.get("wait_s", DEFAULT_WAIT_S))
    try:
        wait_s = float(raw_wait)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"VOICE_WAIT_S deve ser numero: {raw_wait}") from exc
    raw_max = e.get("VOICE_MAX_S", settings.get("max_s", DEFAULT_MAX_S))
    try:
        max_s = float(raw_max)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"VOICE_MAX_S deve ser numero: {raw_max}") from exc
    raw_min_speech = e.get(
        "VOICE_MIN_SPEECH_S", settings.get("min_speech_s", DEFAULT_MIN_SPEECH_S)
    )
    try:
        min_speech_s = float(raw_min_speech)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"VOICE_MIN_SPEECH_S deve ser numero: {raw_min_speech}"
        ) from exc
    return Config(
        opencode_bin=e.get("OPENCODE_BIN", DEFAULT_OPENCODE_BIN),
        timeout_s=timeout_s,
        powershell_exe=e.get("POWERSHELL_EXE", DEFAULT_POWERSHELL_EXE),
        ffmpeg_exe=e.get("FFMPEG_EXE", DEFAULT_FFMPEG_EXE),
        mic_device=e.get("MIC_DEVICE", DEFAULT_MIC_DEVICE),
        whisper_model=e.get("WHISPER_MODEL", DEFAULT_WHISPER_MODEL),
        record_seconds=record_seconds,
        language=e.get("VOICE_LANGUAGE", DEFAULT_LANGUAGE),
        agent_backend=agent_backend,
        agent=e.get("VOICE_AGENT", DEFAULT_AGENT) or None,
        server_url=e.get("OPENCODE_SERVER_URL", DEFAULT_SERVER_URL),
        tts_backend=tts_backend,
        voice_log_path=e.get("VOICE_LOG", DEFAULT_VOICE_LOG),
        piper_exe=e.get("PIPER_EXE", DEFAULT_PIPER_EXE),
        piper_model=e.get("PIPER_MODEL", DEFAULT_PIPER_MODEL),
        ffplay_exe=e.get("FFPLAY_EXE", DEFAULT_FFPLAY_EXE),
        piper_out_wav=e.get("PIPER_OUT_WAV", DEFAULT_PIPER_OUT_WAV),
        vision_model=e.get("VISION_MODEL", DEFAULT_VISION_MODEL),
        vision_trigger=e.get("VISION_TRIGGER", DEFAULT_VISION_TRIGGER),
        vision_png=e.get("VISION_PNG", DEFAULT_VISION_PNG),
        input_mode=input_mode,
        ptt=ptt,
        state_port=state_port,
        state_require_gui=state_require_gui,
        stream_tts=stream_tts,
        stream_idle_ms=stream_idle_ms,
        stream_min_chars=stream_min_chars,
        noise_db=noise_db,
        silence_s=silence_s,
        wait_s=wait_s,
        max_s=max_s,
        min_speech_s=min_speech_s,
    )
