import io
import subprocess
from contextlib import nullcontext

import loop
import pytest
from config import Config

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


def test_do_once_passes_dynamic_ollama_catalog(monkeypatch):
    seen = {}
    monkeypatch.setattr(loop, "opencode_catalog_environment", lambda: {"OPENCODE_CONFIG_CONTENT": "catalog"})
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: (seen.update(kw) or subprocess.CompletedProcess(cmd, 0, "ok", "")))
    loop.do_once("oi", out=io.StringIO(), config=CFG)
    assert seen["env"]["OPENCODE_CONFIG_CONTENT"] == "catalog"


@pytest.mark.parametrize(
    ("env_model", "saved_model", "expected"),
    [
        ("env/model", "saved/model", "env/model"),
        (None, "saved/model", "saved/model"),
    ],
)
def test_voice_turn_model_precedence(monkeypatch, env_model, saved_model, expected):
    if env_model:
        monkeypatch.setenv("AGENT_MODEL", env_model)
    else:
        monkeypatch.delenv("AGENT_MODEL", raising=False)
    monkeypatch.setattr("audio.temporary_audio", lambda config: nullcontext(None))
    monkeypatch.setattr(loop, "record", lambda **kwargs: "/tmp/voice.wav")
    monkeypatch.setattr(loop, "transcribe", lambda *args, **kwargs: "hello")
    monkeypatch.setattr(loop, "speak", lambda *args, **kwargs: None)
    monkeypatch.setattr(loop, "load_settings", lambda: {"agent_model": saved_model})
    client_cfg = Config(opencode_bin="/x/opencode", timeout_s=10, agent_model=env_model, input_mode="fixed")

    class Client:
        _cfg = client_cfg

        def ask(self, task, timeout_s=None):
            self.model_during_turn = self._cfg.agent_model
            return "ok"

    client = Client()
    loop.voice_loop(client=client, iterations=1, record_seconds=1, config=client_cfg)
    assert client.model_during_turn == expected
