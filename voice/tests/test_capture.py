import subprocess, pytest
from config import Config
from capture import record, VoiceError

CFG = Config(opencode_bin="/x/o", timeout_s=10, ffmpeg_exe="/ff/ffmpeg.exe", mic_device="Mic X", record_seconds=5)

def test_record_builds_dshow_command(monkeypatch, tmp_path):
    seen = {}
    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(subprocess, "run", fake_run)
    out = str(tmp_path / "a.wav")
    record(3, out_path=out, config=CFG)
    joined = " ".join(seen["cmd"])
    assert "/ff/ffmpeg.exe" in joined
    assert "-f dshow" in joined
    assert 'audio=Mic X' in joined
    assert "-t 3" in joined
    assert out in seen["cmd"]

def test_missing_ffmpeg_raises(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError()))
    with pytest.raises(VoiceError, match="FFMPEG_EXE=/ff/ffmpeg.exe"):
        record(1, out_path="/tmp/x.wav", config=CFG)
