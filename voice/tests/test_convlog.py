import json

from config import Config
from convlog import log_turn


def _cfg(path):
    return Config(opencode_bin="/x/o", timeout_s=10, voice_log_path=str(path))


def test_writes_jsonl_line(tmp_path):
    path = tmp_path / "voice-log.jsonl"
    log_turn({"transcript": "oi", "response": "ola"}, config=_cfg(path))
    log_turn({"transcript": "t2"}, config=_cfg(path))
    lines = path.read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0]) == {"transcript": "oi", "response": "ola"}
    assert json.loads(lines[1]) == {"transcript": "t2"}


def test_dir_auto_created(tmp_path):
    path = tmp_path / "a" / "b" / "voice-log.jsonl"
    log_turn({"x": 1}, config=_cfg(path))
    assert path.exists()


def test_never_raises_on_bad_path(tmp_path):
    bad = tmp_path / "file"
    bad.write_text("sou arquivo")
    cfg = _cfg(bad / "sub" / "log.jsonl")
    log_turn({"x": 1}, config=cfg)  # nao deve levantar


def test_default_path_used_when_config_none(monkeypatch, tmp_path):
    target = tmp_path / "d.jsonl"
    monkeypatch.setattr("convlog.DEFAULT_VOICE_LOG", str(target))
    log_turn({"x": 1}, config=None)
    assert target.exists()
