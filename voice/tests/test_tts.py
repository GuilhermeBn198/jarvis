import dataclasses
import subprocess
import pytest
from config import Config
from tts import speak, speak_piper, VoiceError

CFG = Config(opencode_bin="/x/opencode", timeout_s=10, powershell_exe="pwsh.exe")
PIPER_CFG = Config(
    opencode_bin="/x/opencode", timeout_s=10, tts_backend="piper",
    piper_exe="/x/piper", piper_model="/x/m.onnx", ffplay_exe="/x/ffplay",
    piper_out_wav=r"C:\out.wav",
)

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


def test_speak_piper_builds_argv_and_uses_stdin(monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    speak_piper("ola piper", to_file=r"D:\bench.wav", config=PIPER_CFG)
    assert len(calls) == 1
    cmd, kw = calls[0]
    assert cmd == ["/x/piper", "-m", "/x/m.onnx", "-f", r"D:\bench.wav"]
    assert kw["input"] == "ola piper\n"


def test_speak_piper_to_file_skips_ffplay(monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    speak_piper("texto", to_file=r"D:\b.wav", config=PIPER_CFG)
    assert len(calls) == 1


def test_speak_piper_plays_via_ffplay_when_no_to_file(monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    speak_piper("texto", config=PIPER_CFG)
    assert calls[0][0][-1] == r"C:\out.wav"
    assert "-nodisp" in calls[1][0]
    assert "-autoexit" in calls[1][0]
    assert calls[1][0][0] == "/x/ffplay"
    assert calls[1][0][-1] == r"C:\out.wav"


def test_speak_piper_empty_is_noop(monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: called.__setitem__("n", called["n"] + 1))
    speak_piper("   ", config=PIPER_CFG)
    assert called["n"] == 0


def test_speak_piper_failure_raises(monkeypatch):
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(subprocess.SubprocessError("x")))
    with pytest.raises(VoiceError):
        speak_piper("x", to_file=r"D:\b.wav", config=PIPER_CFG)


def test_speak_piper_translates_wsl_paths(monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    cfg = dataclasses.replace(
        PIPER_CFG, piper_model="/mnt/c/Users/b/m.onnx",
        piper_out_wav=r"C:\out.wav",
    )
    speak_piper("texto", to_file="/mnt/c/Users/b/bench.wav", config=cfg)
    assert calls[0][2] == r"C:\Users\b\m.onnx"
    assert calls[0][4] == r"C:\Users\b\bench.wav"


def test_speak_dispatches_to_piper(monkeypatch):
    seen = {}
    monkeypatch.setattr("tts.speak_piper",
                        lambda text, to_file=None, config=None: seen.update(text=text))
    speak("usa piper", config=PIPER_CFG)
    assert seen["text"] == "usa piper"


def test_speak_dispatches_to_sapi_by_default(monkeypatch):
    seen = {}
    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    speak("usa sapi", config=CFG)
    assert seen["cmd"][0] == "pwsh.exe"
