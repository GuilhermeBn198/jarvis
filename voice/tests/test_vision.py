import subprocess

import pytest
import vision
from config import Config

CFG = Config(
    opencode_bin="/x/opencode",
    timeout_s=10,
    ffmpeg_exe="/ff/ffmpeg.exe",
    vision_model="opencode-go/deepseek-v4.1-flash",
    vision_png="C:\\Users\\x\\tools\\shot.png",
)


@pytest.fixture(autouse=True)
def _no_server(monkeypatch):
    """Por padrao os testes de `see` usam o fallback `run`."""
    monkeypatch.setattr(vision, "ensure_server", lambda cfg, **k: False)


def test_capture_builds_gdigrab(monkeypatch):
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    out = vision.capture(config=CFG)
    joined = " ".join(seen["cmd"])
    assert "/ff/ffmpeg.exe" in joined
    assert "-f gdigrab" in joined
    assert "-i desktop" in joined
    assert out == "/mnt/c/Users/x/tools/shot.png"  # WSL path returned


def test_capture_failure_raises(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError())
    )
    with pytest.raises(Exception):  # noqa: B017
        vision.capture(config=CFG)


def test_capture_converts_wsl_out_path(monkeypatch):
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    out = vision.capture(out_path="/mnt/c/Users/x/shot.png", config=CFG)
    assert "C:\\Users\\x\\shot.png" in seen["cmd"]
    assert out == "/mnt/c/Users/x/shot.png"


def test_see_empty_output_raises(monkeypatch):
    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, "   \n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(vision.VoiceError, match="nao retornou resposta"):
        vision.see("o que tem?", "/mnt/c/Users/x/tools/shot.png", config=CFG)


def test_see_message_before_f(monkeypatch):
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "uma tela com x\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    out = vision.see("o que tem na tela?", "/mnt/c/Users/x/tools/shot.png", config=CFG)
    cmd = seen["cmd"]
    assert cmd[0] == "/x/opencode"
    assert "o que tem na tela?" in cmd
    assert "-m" in cmd and "opencode-go/deepseek-v4.1-flash" in cmd
    assert "-f" in cmd and "/mnt/c/Users/x/tools/shot.png" in cmd
    assert cmd.index("o que tem na tela?") < cmd.index("-f")  # msg antes de -f
    assert out == "uma tela com x"


def test_see_uses_serve_when_healthy(monkeypatch):
    seen = {}
    monkeypatch.setattr(vision, "ensure_server", lambda cfg, **k: True)

    class FakeServe:
        def __init__(self, cfg):
            seen["cfg"] = cfg

        def see(self, prompt, png, model_id=None):
            seen["call"] = (prompt, png, model_id)
            return "tela via serve"

    monkeypatch.setattr(vision, "ServeClient", FakeServe)

    def no_run(*a, **k):
        raise AssertionError("nao deveria usar `run`")

    monkeypatch.setattr(subprocess, "run", no_run)
    out = vision.see("o que tem?", "/mnt/c/x/shot.png", config=CFG)
    assert out == "tela via serve"
    assert seen["call"] == (
        "o que tem?",
        "/mnt/c/x/shot.png",
        CFG.vision_model,
    )


def test_see_falls_back_to_run_on_serve_error(monkeypatch):
    from agent_client import AgentError

    monkeypatch.setattr(vision, "ensure_server", lambda cfg, **k: True)

    class FakeServe:
        def __init__(self, cfg):
            pass

        def see(self, *a, **k):
            raise AgentError("sessao morreu")

    monkeypatch.setattr(vision, "ServeClient", FakeServe)

    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "tela via run\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    out = vision.see("x", "/mnt/c/x/shot.png", config=CFG)
    assert out == "tela via run"
    assert seen["cmd"][1] == "run"


def test_see_uses_short_wait_when_ensuring_server(monkeypatch):
    seen = {}
    monkeypatch.setattr(vision, "ensure_server", lambda cfg, **k: seen.update(k) or False)

    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, "tela via run\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    vision.see("x", "/mnt/c/x/shot.png", config=CFG)
    assert seen.get("wait_s") == 3


def test_see_falls_back_to_run_when_server_down(monkeypatch):
    monkeypatch.setattr(vision, "ensure_server", lambda cfg, **k: False)

    def boom(*a, **k):
        raise AssertionError("nao deveria usar `serve`")

    class FakeServe:
        def __init__(self, cfg):
            boom()

    monkeypatch.setattr(vision, "ServeClient", FakeServe)

    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "tela via run\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    out = vision.see("o que tem?", "/mnt/c/x/shot.png", config=CFG)
    assert out == "tela via run"
    assert seen["cmd"][1] == "run"


def test_see_via_run_uses_project_root_cwd(monkeypatch):
    seen = {}

    def fake_run(cmd, **kw):
        seen["kw"] = kw
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    cfg = Config(opencode_bin="/x/o", timeout_s=10, project_root="/repo")
    vision._see_via_run(cfg, "q", "/tmp/x.png")
    assert seen["kw"]["cwd"] == "/repo"


def test_see_aggregates_serve_and_run_causes_on_double_failure(monkeypatch):
    from agent_client import AgentError

    monkeypatch.setattr(vision, "ensure_server", lambda cfg, **k: True)

    class FakeServe:
        def __init__(self, cfg):
            pass

        def see(self, *a, **k):
            raise AgentError("falha ao falar com o servidor (HTTP Error 500)")

    monkeypatch.setattr(vision, "ServeClient", FakeServe)

    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(
            cmd,
            1,
            "",
            "\x1b[31mModel not found: opencode-go/deepseek-v4.1-flash\x1b[0m",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(vision.VoiceError) as excinfo:
        vision.see("o que tem?", "/mnt/c/x/shot.png", config=CFG)
    msg = str(excinfo.value)
    assert "serve" in msg
    assert "HTTP Error 500" in msg
    assert "Model not found" in msg
    assert "\x1b[" not in msg


def test_see_via_run_strips_ansi_from_stderr(monkeypatch):
    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 1, "", "\x1b[31mModel not found\x1b[0m\n")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(vision.VoiceError) as excinfo:
        vision._see_via_run(CFG, "q", "/tmp/x.png")
    msg = str(excinfo.value)
    assert "Model not found" in msg
    assert "\x1b[" not in msg
