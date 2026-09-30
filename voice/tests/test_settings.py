import json

from settings import (
    DEFAULT_SETTINGS_PATH,
    SETTINGS_KEYS,
    load_settings,
    save_settings,
)


def test_load_settings_missing_returns_empty(tmp_path):
    assert load_settings(str(tmp_path / "nope.json")) == {}


def test_load_settings_ignores_unknown_and_bad_file(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"noise_db": -25, "nope": 1}), encoding="utf-8")
    assert load_settings(str(p)) == {"noise_db": -25}
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    assert load_settings(str(bad)) == {}
    arr = tmp_path / "arr.json"
    arr.write_text("[1,2]", encoding="utf-8")
    assert load_settings(str(arr)) == {}


def test_save_settings_coerces_and_persists(tmp_path):
    p = str(tmp_path / "s.json")
    out = save_settings(
        {"noise_db": "-30", "silence_s": "1.5", "stream_tts": "off", "junk": 1},
        path=p,
    )
    assert out["noise_db"] == -30
    assert out["silence_s"] == 1.5
    assert out["stream_tts"] is False
    assert "junk" not in out
    assert load_settings(p) == out


def test_save_settings_merges_and_drops_invalid(tmp_path):
    p = str(tmp_path / "s.json")
    save_settings({"noise_db": -25}, path=p)
    out = save_settings({"silence_s": "x", "wait_s": 9}, path=p)
    assert out["noise_db"] == -25
    assert out["wait_s"] == 9.0
    assert "silence_s" not in out


def test_settings_keys_are_the_panel_surface():
    assert "noise_db" in SETTINGS_KEYS
    assert "stream_tts" in SETTINGS_KEYS
    assert DEFAULT_SETTINGS_PATH.endswith("jarvis/settings.json")


def test_save_settings_persists_mic_device(tmp_path):
    p = str(tmp_path / "s.json")
    out = save_settings({"mic_device": "  Mic Legal  "}, path=p)
    assert out["mic_device"] == "Mic Legal"
    assert "mic_device" in SETTINGS_KEYS
