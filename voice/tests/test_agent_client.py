import subprocess
import pytest
from config import Config
from agent_client import RunClient, AgentError

CFG = Config(opencode_bin="/x/opencode", timeout_s=10)

def test_ask_returns_stdout(monkeypatch):
    seen = {}
    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="  resposta  \n", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    out = RunClient(CFG).ask("faca algo")
    assert out == "resposta"
    assert seen["cmd"] == ["/x/opencode", "run", "--pure", "faca algo"]

def test_empty_task_raises():
    with pytest.raises(AgentError):
        RunClient(CFG).ask("   ")

def test_missing_binary_raises(monkeypatch):
    def fake_run(*a, **k):
        raise FileNotFoundError()
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(AgentError) as exc:
        RunClient(CFG).ask("x")
    assert "nao encontrado" in str(exc.value)

def test_not_executable_binary_raises(monkeypatch):
    def fake_run(*a, **k):
        raise PermissionError()
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(AgentError) as exc:
        RunClient(CFG).ask("x")
    assert "executavel" in str(exc.value)

def test_generic_oserror_raises(monkeypatch):
    def fake_run(*a, **k):
        raise OSError("boom")
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(AgentError) as exc:
        RunClient(CFG).ask("x")
    assert "falha ao executar" in str(exc.value)

def test_empty_stdout_raises(monkeypatch):
    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(AgentError):
        RunClient(CFG).ask("x")

def test_timeout_raises(monkeypatch):
    def fake_run(*a, **k):
        raise subprocess.TimeoutExpired("cmd", 1)
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(AgentError):
        RunClient(CFG).ask("x")

def test_nonzero_exit_raises(monkeypatch):
    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 2, stdout="", stderr="boom")
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(AgentError):
        RunClient(CFG).ask("x")
