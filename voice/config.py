import os
from dataclasses import dataclass

DEFAULT_OPENCODE_BIN = os.path.expanduser("~/.opencode/bin/opencode")
DEFAULT_TIMEOUT_S = 300
DEFAULT_POWERSHELL_EXE = "powershell.exe"
DEFAULT_FFMPEG_EXE = (
    "/mnt/c/Users/bguil/tools/ffmpeg/ffmpeg-master-latest-win64-gpl/bin/ffmpeg.exe"
)
DEFAULT_MIC_DEVICE = "Microphone (FIFINE Microphone)"
DEFAULT_WHISPER_MODEL = "base"
DEFAULT_RECORD_SECONDS = 5
DEFAULT_LANGUAGE = "pt"
DEFAULT_AGENT_BACKEND = "run"
DEFAULT_SERVER_URL = "http://127.0.0.1:4096"
DEFAULT_TTS_BACKEND = "sapi"
DEFAULT_PIPER_EXE = "/mnt/c/Users/bguil/tools/piper/piper/piper.exe"
DEFAULT_PIPER_MODEL = "/mnt/c/Users/bguil/tools/piper/voices/pt_BR-faber-medium.onnx"
DEFAULT_FFPLAY_EXE = (
    "/mnt/c/Users/bguil/tools/ffmpeg/ffmpeg-master-latest-win64-gpl/bin/ffplay.exe"
)
DEFAULT_PIPER_OUT_WAV = r"C:\Users\bguil\tools\piper\out.wav"


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
    server_url: str = DEFAULT_SERVER_URL
    tts_backend: str = DEFAULT_TTS_BACKEND
    piper_exe: str = DEFAULT_PIPER_EXE
    piper_model: str = DEFAULT_PIPER_MODEL
    ffplay_exe: str = DEFAULT_FFPLAY_EXE
    piper_out_wav: str = DEFAULT_PIPER_OUT_WAV


def load_config(env: dict | None = None) -> Config:
    e = os.environ if env is None else env
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
    return Config(
        opencode_bin=e.get("OPENCODE_BIN", DEFAULT_OPENCODE_BIN),
        timeout_s=timeout_s,
        powershell_exe=e.get("POWERSHELL_EXE", DEFAULT_POWERSHELL_EXE),
        ffmpeg_exe=e.get("FFMPEG_EXE", DEFAULT_FFMPEG_EXE),
        mic_device=e.get("MIC_DEVICE", DEFAULT_MIC_DEVICE),
        whisper_model=e.get("WHISPER_MODEL", DEFAULT_WHISPER_MODEL),
        record_seconds=record_seconds,
        language=e.get("VOICE_LANGUAGE", DEFAULT_LANGUAGE),
        agent_backend=e.get("AGENT_BACKEND", DEFAULT_AGENT_BACKEND),
        server_url=e.get("OPENCODE_SERVER_URL", DEFAULT_SERVER_URL),
        tts_backend=e.get("TTS_BACKEND", DEFAULT_TTS_BACKEND),
        piper_exe=e.get("PIPER_EXE", DEFAULT_PIPER_EXE),
        piper_model=e.get("PIPER_MODEL", DEFAULT_PIPER_MODEL),
        ffplay_exe=e.get("FFPLAY_EXE", DEFAULT_FFPLAY_EXE),
        piper_out_wav=e.get("PIPER_OUT_WAV", DEFAULT_PIPER_OUT_WAV),
    )
