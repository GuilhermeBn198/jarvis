import io
import subprocess

import pytest

from config import Config
import loop

CFG = Config(opencode_bin="/x/opencode", timeout_s=10, agent="chat")


@pytest.fixture(autouse=True)
def _no_convlog(monkeypatch):
    monkeypatch.setattr("loop.log_turn", lambda *a, **k: None)


def test_do_uses_agent_act(monkeypatch):
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "feito", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    out = io.StringIO()
    loop.do_once("abra o notepad", out=out, config=CFG)
    assert "--agent" in seen["cmd"] and "act" in seen["cmd"]
    assert "--pure" not in seen["cmd"]
    assert "abra o notepad" in seen["cmd"]
    assert "feito" in out.getvalue()


def test_do_restores_idle_when_opencode_missing(monkeypatch):
    class FakeHub:
        def __init__(self):
            self.states = []

        def set(self, state):
            self.states.append(state)

    def boom(cmd, **kw):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", boom)
    hub = FakeHub()
    loop.do_once("abra algo", out=io.StringIO(), err=io.StringIO(), config=CFG, hub=hub)
    assert hub.states[0] == "acting"
    assert hub.states[-1] == "idle"


def test_do_once_runs_opencode_in_project_root(monkeypatch):
    seen = {}
    def fake_run(cmd, **kw):
        seen["kw"] = kw
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    cfg = Config(opencode_bin="/x/o", timeout_s=10, project_root="/repo")
    loop.do_once("oi", out=io.StringIO(), err=io.StringIO(), config=cfg)
    assert seen["kw"]["cwd"] == "/repo"
