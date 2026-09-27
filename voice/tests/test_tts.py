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
