#!/usr/bin/env python3
"""Exercise Linux Piper output and PTT/VAD/STT with isolated Pulse audio."""
from __future__ import annotations

import difflib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
import uuid
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "voice"))


def pulse_monitor_source(sink_name: str) -> str:
    if not re.fullmatch(r"jarvis_linux_audio_test_[A-Za-z0-9_]+", sink_name):
        raise ValueError("source Pulse must belong to the isolated Jarvis test sink")
    return f"{sink_name}.monitor"


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if char.isalnum())


def transcript_matches(actual: str, expected: str, threshold: float = 0.72) -> bool:
    actual_text, expected_text = _normalize(actual), _normalize(expected)
    if not actual_text or not expected_text:
        return False
    return difflib.SequenceMatcher(None, actual_text, expected_text).ratio() >= threshold


def _executable(name: str, *fallbacks: str) -> str:
    for candidate in (name, *fallbacks):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
        if os.path.isabs(candidate) and os.access(candidate, os.X_OK):
            return candidate
    raise RuntimeError(f"executable not found: {name}")


def _add_private_python_path(private_python: Path) -> None:
    path = str(private_python)
    if path not in sys.path:
        sys.path.insert(0, path)
    old_pythonpath = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = os.pathsep.join(
        item for item in (path, old_pythonpath) if item
    )


def _duration(ffprobe: str, wav: Path) -> float:
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(wav)],
        capture_output=True, text=True, check=True, timeout=15,
    )
    return float(result.stdout.strip())


def _play(paplay: str, sink: str, wav: Path) -> None:
    result = subprocess.run(
        [paplay, "--device", sink, str(wav)],
        capture_output=True, text=True, timeout=20,
    )
    if result.returncode:
        raise RuntimeError(f"paplay failed: {result.stderr.strip()}")


def _capture_and_check(label: str, wav: Path, cfg, ffprobe: str, expected: str) -> None:
    from stt import transcribe

    duration = _duration(ffprobe, wav)
    transcript = transcribe(str(wav), config=cfg)
    if duration < 0.8 or not transcript_matches(transcript, expected):
        raise RuntimeError(
            f"{label} capture failed: duration={duration:.2f}s, "
            f"transcript={transcript!r}"
        )
    print(f"{label}: duration={duration:.2f}s transcript={transcript!r}")


def run() -> None:
    if sys.platform != "linux":
        raise RuntimeError("this smoke test requires Linux")

    pactl = _executable("pactl")
    paplay = _executable("paplay")
    ffmpeg = _executable("ffmpeg")
    ffprobe = _executable("ffprobe")
    piper = _executable("piper", "/usr/lib/jarvis/python/bin/piper")
    private_python = Path(piper).resolve().parent.parent
    if private_python.is_dir():
        _add_private_python_path(private_python)
    os.environ.setdefault("HF_HUB_OFFLINE", "1")

    from capture import record_auto, record_ptt
    from config import load_config
    from tts import speak_piper

    cfg = load_config()
    if not Path(cfg.piper_model).is_file():
        raise RuntimeError(f"Piper voice model not found: {cfg.piper_model}")

    sink = f"jarvis_linux_audio_test_{os.getpid()}_{uuid.uuid4().hex[:8]}"
    source = pulse_monitor_source(sink)
    loaded = subprocess.run(
        [pactl, "load-module", "module-null-sink", f"sink_name={sink}",
         "sink_properties=device.description=JarvisLinuxSyntheticInput"],
        capture_output=True, text=True, check=True, timeout=15,
    )
    module_id = loaded.stdout.strip()
    try:
        sources = subprocess.run(
            [pactl, "list", "short", "sources"],
            capture_output=True, text=True, check=True, timeout=15,
        ).stdout.splitlines()
        if not any(len(line.split()) > 1 and line.split()[1] == source for line in sources):
            raise RuntimeError(f"isolated Pulse monitor source not found: {source}")

        cfg = replace(
            cfg, platform="linux", audio_backend="pulse", mic_device=source,
            ffmpeg_exe=ffmpeg, piper_exe=piper,
        )
        expected = "O Jarvis está funcionando em Linux."
        with tempfile.TemporaryDirectory(prefix="jarvis-linux-virtual-audio-") as temp:
            directory = Path(temp)
            synthetic = directory / "synthetic.wav"
            tts_output = directory / "tts-output.wav"
            ptt_wav = directory / "ptt.wav"
            vad_wav = directory / "vad.wav"
            speak_piper(expected, to_file=str(synthetic), config=cfg)

            output_capture = subprocess.Popen(
                [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
                 "-y", "-f", "pulse", "-i", source, "-t", "8",
                 str(tts_output)],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
            )
            old_pulse_sink = os.environ.get("PULSE_SINK")
            try:
                time.sleep(0.35)
                os.environ["PULSE_SINK"] = sink
                speak_piper(expected, config=cfg)
            finally:
                if old_pulse_sink is None:
                    os.environ.pop("PULSE_SINK", None)
                else:
                    os.environ["PULSE_SINK"] = old_pulse_sink
                if output_capture.poll() is None:
                    try:
                        _, capture_error = output_capture.communicate(timeout=15)
                    except subprocess.TimeoutExpired:
                        output_capture.terminate()
                        _, capture_error = output_capture.communicate(timeout=5)
                else:
                    _, capture_error = output_capture.communicate()
            if output_capture.returncode:
                raise RuntimeError(f"TTS Pulse monitor failed: {capture_error.strip()}")
            _capture_and_check("TTS output", tts_output, cfg, ffprobe, expected)

            def ptt_prompt(message: str) -> None:
                if message.startswith("Fale agora"):
                    _play(paplay, sink, synthetic)
                    time.sleep(0.35)

            record_ptt(str(ptt_wav), config=cfg, prompt_fn=ptt_prompt)
            _capture_and_check("PTT", ptt_wav, cfg, ffprobe, expected)

            playback_errors: list[BaseException] = []

            def delayed_playback() -> None:
                try:
                    time.sleep(0.7)
                    _play(paplay, sink, synthetic)
                except BaseException as exc:
                    playback_errors.append(exc)

            player = threading.Thread(target=delayed_playback, daemon=True)
            player.start()
            record_auto(
                str(vad_wav), config=cfg, max_s=10, wait_s=5,
                silence_s=0.55, noise_db=-45, min_speech_s=0.55,
            )
            player.join(timeout=22)
            if player.is_alive():
                raise RuntimeError("synthetic audio playback did not finish")
            if playback_errors:
                raise RuntimeError(f"synthetic audio playback failed: {playback_errors[0]}")
            _capture_and_check("VAD", vad_wav, cfg, ffprobe, expected)
        print("PASS: Piper -> isolated Pulse output; synthetic monitor -> PTT/VAD -> faster-whisper")
        print("The physical microphone was not opened; all generated files were removed.")
    finally:
        subprocess.run(
            [pactl, "unload-module", module_id],
            capture_output=True, text=True, timeout=15,
        )
        print(f"cleanup: unloaded temporary Pulse module {module_id}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
