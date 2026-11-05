import pytest

from scripts import linux_virtual_audio_smoke as smoke
from scripts.linux_virtual_audio_smoke import pulse_monitor_source, transcript_matches


def test_transcript_match_accepts_small_synthetic_speech_recognition_errors():
    assert transcript_matches(
        "O javise está funcionando em lênus.",
        "O Jarvis está funcionando em Linux.",
    )


def test_transcript_match_rejects_unrelated_audio():
    assert not transcript_matches(
        "A previsão do tempo está ensolarada.",
        "O Jarvis está funcionando em Linux.",
    )


def test_pulse_monitor_source_requires_the_isolated_test_sink_prefix():
    assert pulse_monitor_source("jarvis_linux_audio_test_123") == (
        "jarvis_linux_audio_test_123.monitor"
    )
    with pytest.raises(ValueError):
        pulse_monitor_source("default")


def test_private_runtime_path_is_added_to_current_process_and_children(
    monkeypatch, tmp_path
):
    private_python = tmp_path / "private-python"
    private_python.mkdir()
    monkeypatch.setattr(smoke.sys, "path", ["existing-path"])
    monkeypatch.delenv("PYTHONPATH", raising=False)

    smoke._add_private_python_path(private_python)

    assert smoke.sys.path[0] == str(private_python)
    assert smoke.sys.path[1] == "existing-path"
    assert smoke.os.environ["PYTHONPATH"] == str(private_python)
