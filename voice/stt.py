from config import Config, load_config
from tts import VoiceError


def _load_model(cfg: Config):
    from faster_whisper import WhisperModel
    return WhisperModel(cfg.whisper_model, device="cpu", compute_type="int8")


def transcribe(wav_path: str, config: Config | None = None) -> str:
    cfg = config or load_config()
    try:
        segments, _info = _load_model(cfg).transcribe(
            wav_path, language=cfg.language, beam_size=1
        )
    except Exception as exc:  # noqa: BLE001
        raise VoiceError(f"falha na transcricao: {exc}") from exc
    return " ".join(s.text.strip() for s in segments).strip()
