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
