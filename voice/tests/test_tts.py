import subprocess
import pytest
from config import Config
from tts import speak, VoiceError

CFG = Config(opencode_bin="/x/opencode", timeout_s=10, powershell_exe="pwsh.exe")

def test_speak_runs_powershell_encodedcommand(monkeypatch):
    seen = {}
    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    speak("ola mundo", config=CFG)
    assert seen["cmd"][0] == "pwsh.exe"
    assert "-EncodedCommand" in seen["cmd"]

def test_empty_text_is_noop(monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: called.__setitem__("n", called["n"]+1))
    speak("   ", config=CFG)
    assert called["n"] == 0

def test_failure_raises(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(subprocess.SubprocessError("x")))
    with pytest.raises(VoiceError):
        speak("x", config=CFG)

def test_nonzero_returncode_raises(monkeypatch):
    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="err")
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(VoiceError):
        speak("x", config=CFG)

def test_to_file_uses_setoutputtowavefile(monkeypatch):
    import base64
    seen = {}
    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    speak("ola", to_file="/tmp/out.wav", config=CFG)
    encoded = seen["cmd"][seen["cmd"].index("-EncodedCommand") + 1]
    script = base64.b64decode(encoded).decode("utf-16-le")
    assert "SetOutputToWaveFile" in script
    assert "/tmp/out.wav" not in script
