import io
from loop import run_stream
from agent_client import AgentError

class FakeClient:
    def __init__(self, replies): self._replies = replies
    def ask(self, task, timeout_s=None): return self._replies[task]

def test_run_stream_answers_each_line():
    out = io.StringIO()
    run_stream(io.StringIO("oi\nola\n"), out, FakeClient({"oi": "R1", "ola": "R2"}))
    assert out.getvalue().splitlines() == ["R1", "R2"]

def test_run_stream_skips_blank_and_reports_errors():
    class ErrClient:
        def ask(self, task, timeout_s=None): raise AgentError("falhou")
    out, err = io.StringIO(), io.StringIO()
    run_stream(io.StringIO("\nboa\n"), out, ErrClient(), err)
    assert out.getvalue() == ""
    assert "falhou" in err.getvalue()
