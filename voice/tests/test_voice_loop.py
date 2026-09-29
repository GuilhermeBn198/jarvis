import io
import time

import pytest

import loop as loop_mod
from config import Config, load_config
from loop import _parse_once, main, voice_loop
from tts import VoiceError

CFG = Config(opencode_bin="/x/o", timeout_s=10, record_seconds=1, input_mode="fixed", ptt=False)
AUTO_CFG = Config(opencode_bin="/x/o", timeout_s=10, record_seconds=1, input_mode="auto")


@pytest.fixture(autouse=True)
def _no_convlog(monkeypatch):
    monkeypatch.setattr("loop.log_turn", lambda *a, **k: None)


def test_voice_loop_logs_turn_and_speaks_sanitized(monkeypatch):
    records = []
    spoken_texts = []
    monkeypatch.setattr("loop.record", lambda **k: "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: "faca algo")
    monkeypatch.setattr("loop.speak", lambda text, **k: spoken_texts.append(text))
    monkeypatch.setattr(
        "loop.log_turn", lambda rec, config=None: records.append(rec)
    )

    class Client:
        def ask(self, task, timeout_s=None):
            return "**Resposta** `crua`\n```python\nprint(1)\n```"

    voice_loop(client=Client(), iterations=1, record_seconds=1, config=CFG)
    assert spoken_texts == ["Resposta crua bloco de código omitido"]
    assert len(records) == 1
    rec = records[0]
    assert rec["transcript"] == "faca algo"
    assert rec["response"] == "**Resposta** `crua`\n```python\nprint(1)\n```"
    assert rec["spoken"] == "Resposta crua bloco de código omitido"
    assert rec["agent_backend"] == CFG.agent_backend
    assert rec["tts_backend"] == CFG.tts_backend
    assert rec["error"] is None
    for key in ("ts", "record_s", "stt_s", "agent_s", "tts_s"):
        assert key in rec


def test_voice_loop_logs_agent_error(monkeypatch):
    records = []
    monkeypatch.setattr("loop.record", lambda **k: "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: "faca algo")
    monkeypatch.setattr("loop.speak", lambda text, **k: None)
    monkeypatch.setattr(
        "loop.log_turn", lambda rec, config=None: records.append(rec)
    )

    from agent_client import AgentError

    class Client:
        def ask(self, task, timeout_s=None):
            raise AgentError("boom")

    voice_loop(client=Client(), iterations=1, record_seconds=1, config=CFG)
    assert len(records) == 1
    assert records[0]["error"] == "boom"
    assert records[0]["response"] == "erro: boom"


def test_voice_loop_orchestrates(monkeypatch):
    calls = []
    monkeypatch.setattr("loop.record", lambda **k: calls.append("record") or "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: calls.append("stt") or "faca algo")
    monkeypatch.setattr("loop.speak", lambda text, **k: calls.append("tts"))

    class Client:
        def ask(self, task, timeout_s=None):
            calls.append("ask")
            return "resposta"
    voice_loop(client=Client(), iterations=1, record_seconds=1, config=CFG)
    assert calls == ["record", "stt", "ask", "tts"]

def test_voice_loop_uses_ptt_when_enabled(monkeypatch):
    calls = []
    ptt_cfg = Config(opencode_bin="/x/o", timeout_s=10, record_seconds=1, input_mode="ptt", ptt=True)
    monkeypatch.setattr("loop.record", lambda **k: calls.append("record") or "/tmp/a.wav")
    monkeypatch.setattr("loop.record_ptt", lambda **k: calls.append("record_ptt") or "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: "")

    class Client:
        def ask(self, *a, **k):
            return "x"
    voice_loop(client=Client(), iterations=1, record_seconds=1, config=ptt_cfg)
    assert calls == ["record_ptt"]


def test_voice_loop_uses_fixed_window_when_ptt_disabled(monkeypatch):
    calls = []
    monkeypatch.setattr("loop.record", lambda **k: calls.append("record") or "/tmp/a.wav")
    monkeypatch.setattr("loop.record_ptt", lambda **k: calls.append("record_ptt") or "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: "")

    class Client:
        def ask(self, *a, **k):
            return "x"
    voice_loop(client=Client(), iterations=1, record_seconds=1, config=CFG)
    assert calls == ["record"]


def test_voice_loop_auto_no_speech_skips_agent(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "loop.record_auto", lambda **k: calls.append("record_auto") or ""
    )
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: calls.append("stt") or "oi")
    monkeypatch.setattr("loop.speak", lambda text, **k: calls.append("tts"))
    err = io.StringIO()

    class Client:
        def ask(self, *a, **k):
            calls.append("ask")
            return "x"
    voice_loop(client=Client(), iterations=1, config=AUTO_CFG, err=err)
    assert calls == ["record_auto"]
    assert "nada detectado" in err.getvalue()


def test_voice_loop_auto_with_speech_transcribes_asks_speaks(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "loop.record_auto",
        lambda **k: calls.append("record_auto") or "/tmp/a.wav",
    )
    monkeypatch.setattr(
        "loop.transcribe", lambda wav, **k: calls.append("stt") or "faca algo"
    )
    monkeypatch.setattr("loop.speak", lambda text, **k: calls.append("tts"))

    class Client:
        def ask(self, task, timeout_s=None):
            calls.append("ask")
            return "resposta"
    voice_loop(client=Client(), iterations=1, config=AUTO_CFG)
    assert calls == ["record_auto", "stt", "ask", "tts"]


def test_voice_loop_empty_transcript_skips_agent(monkeypatch):
    calls = []
    monkeypatch.setattr("loop.record", lambda **k: calls.append("record") or "/tmp/a.wav")
    monkeypatch.setattr("loop.record_ptt", lambda **k: calls.append("record_ptt") or "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: calls.append("stt") or "")
    monkeypatch.setattr("loop.speak", lambda text, **k: calls.append("tts"))
    class Client:
        def ask(self, *a, **k):
            calls.append("ask"); return "x"
    voice_loop(client=Client(), iterations=1, record_seconds=1, config=CFG)
    assert calls == ["record", "stt"]
    assert "ask" not in calls


def test_voice_loop_forwards_config(monkeypatch):
    seen = {}
    monkeypatch.setattr("loop.record", lambda **k: seen.update(rec=k) or "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: seen.update(stt=k) or "")
    monkeypatch.setattr("loop.speak", lambda text, **k: None)

    class Client:
        def ask(self, task, timeout_s=None):
            return "x"
    voice_loop(client=Client(), iterations=1, record_seconds=1, config=CFG)
    assert seen["rec"]["config"] is CFG
    assert seen["stt"]["config"] is CFG


def test_voice_loop_contains_voiceerror(monkeypatch):
    calls = []
    def boom(**k):
        calls.append("record")
        raise VoiceError("sem mic")
    monkeypatch.setattr("loop.record", boom)
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: calls.append("stt") or "x")
    monkeypatch.setattr("loop.speak", lambda text, **k: calls.append("tts"))
    err = io.StringIO()

    class Client:
        def ask(self, task, timeout_s=None):
            calls.append("ask")
            return "x"
    voice_loop(client=Client(), iterations=2, record_seconds=1, config=CFG, err=err)
    assert calls == ["record", "record"]
    assert "sem mic" in err.getvalue()


def test_voice_loop_falls_back_to_text_when_speak_fails(monkeypatch):
    monkeypatch.setattr("loop.record", lambda **k: "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: "faca algo")

    def boom(text, **k):
        raise VoiceError("SAPI indisponivel")
    monkeypatch.setattr("loop.speak", boom)
    err = io.StringIO()

    class Client:
        def ask(self, task, timeout_s=None):
            return "resposta falada"
    voice_loop(client=Client(), iterations=1, record_seconds=1, config=CFG, err=err)
    assert "[fallback texto] resposta falada" in err.getvalue()


def test_voice_loop_aborts_after_consecutive_errors(monkeypatch):
    calls = []

    def boom(**k):
        calls.append("record")
        raise VoiceError("sem mic")
    monkeypatch.setattr("loop.record", boom)
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: "x")
    monkeypatch.setattr("loop.speak", lambda text, **k: None)
    err = io.StringIO()

    class Client:
        def ask(self, task, timeout_s=None):
            return "x"
    voice_loop(client=Client(), iterations=0, record_seconds=1, config=CFG,
               err=err, max_consecutive_errors=3)
    assert len(calls) == 3
    assert "abortando" in err.getvalue()


def test_voice_loop_resets_consecutive_errors_on_success(monkeypatch):
    state = {"i": 0}

    def rec(**k):
        state["i"] += 1
        if state["i"] % 2 == 1:
            raise VoiceError("falha intermitente")
        return "/tmp/a.wav"
    monkeypatch.setattr("loop.record", rec)
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: "faca algo")
    monkeypatch.setattr("loop.speak", lambda text, **k: None)

    class Client:
        def ask(self, task, timeout_s=None):
            return "r"
    voice_loop(client=Client(), iterations=4, record_seconds=1, config=CFG,
               max_consecutive_errors=2)
    assert state["i"] == 4


def test_voice_loop_empty_transcript_writes_stderr(monkeypatch):
    monkeypatch.setattr("loop.record", lambda **k: "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: "")
    monkeypatch.setattr("loop.speak", lambda text, **k: None)
    err = io.StringIO()

    class Client:
        def ask(self, *a, **k):
            return "x"
    voice_loop(client=Client(), iterations=1, record_seconds=1, config=CFG, err=err)
    assert "nada transcrito" in err.getvalue()


def test_voice_loop_builds_client_when_none(monkeypatch):
    made = {}
    monkeypatch.setattr("loop.record", lambda **k: "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: "faca algo")
    monkeypatch.setattr("loop.speak", lambda text, **k: None)

    class Client:
        def ask(self, task, timeout_s=None):
            return "r"

    def fake_resolve(cfg, err=None):
        made["cfg"] = cfg
        return Client()
    monkeypatch.setattr("loop.resolve_client", fake_resolve)
    voice_loop(client=None, iterations=1, record_seconds=1, config=CFG)
    assert made["cfg"] is CFG


def test_parse_once():
    assert _parse_once(["--voice"]) == 0
    assert _parse_once(["--voice", "--once", "3"]) == 3
    assert _parse_once(["--voice", "--once"]) == 1
    assert _parse_once(["--voice", "--once", "x"]) == 1


def test_main_voice_parses_iterations_and_stops(monkeypatch):
    seen = {}
    monkeypatch.setattr(loop_mod, "ensure_server", lambda cfg: True)
    monkeypatch.setattr(loop_mod, "make_client", lambda cfg: "client")
    monkeypatch.setattr(loop_mod, "StateHub", lambda *a, **k: None)
    monkeypatch.setattr(loop_mod.sys, "stderr", io.StringIO())
    monkeypatch.setattr(
        loop_mod, "voice_loop",
        lambda c, **k: seen.update(n=k.get("iterations"), hub=k.get("hub")),
    )
    assert main(["--voice", "--once", "1"]) == 0
    assert seen["n"] == 1
    assert seen["hub"] is None


def test_main_rejects_once_zero(monkeypatch):
    called = []
    monkeypatch.setattr(loop_mod, "ensure_server", lambda cfg: True)
    monkeypatch.setattr(loop_mod, "make_client", lambda cfg: "client")
    monkeypatch.setattr(loop_mod, "StateHub", lambda *a, **k: None)
    monkeypatch.setattr(loop_mod.sys, "stderr", io.StringIO())
    monkeypatch.setattr(loop_mod, "voice_loop", lambda c, **k: called.append(k))
    assert main(["--voice", "--once", "0"]) == 2
    assert called == []


def test_main_voice_handles_keyboard_interrupt(monkeypatch):
    monkeypatch.setattr(loop_mod, "ensure_server", lambda cfg: True)
    monkeypatch.setattr(loop_mod, "make_client", lambda cfg: "client")
    monkeypatch.setattr(loop_mod, "StateHub", lambda *a, **k: None)
    monkeypatch.setattr(loop_mod.sys, "stderr", io.StringIO())

    def boom(c, **k):
        raise KeyboardInterrupt
    monkeypatch.setattr(loop_mod, "voice_loop", boom)
    assert main(["--voice"]) == 0


def test_resolve_client_serve_healthy_uses_make_client(monkeypatch):
    monkeypatch.setattr(loop_mod, "ensure_server", lambda cfg: True)
    sentinel = object()
    monkeypatch.setattr(loop_mod, "make_client", lambda cfg: sentinel)
    cfg = Config(opencode_bin="/x/o", timeout_s=10, agent_backend="serve")
    assert loop_mod.resolve_client(cfg, io.StringIO()) is sentinel


def test_resolve_client_serve_down_falls_back_to_run(monkeypatch):
    monkeypatch.setattr(loop_mod, "ensure_server", lambda cfg: False)
    called = []
    monkeypatch.setattr(loop_mod, "make_client", lambda cfg: called.append(cfg))
    cfg = Config(opencode_bin="/x/o", timeout_s=10, agent_backend="serve")
    err = io.StringIO()
    client = loop_mod.resolve_client(cfg, err)
    assert isinstance(client, loop_mod.RunClient)
    assert called == []
    assert "[aviso]" in err.getvalue()
    assert "run" in err.getvalue()


def test_resolve_client_run_backend_skips_ensure(monkeypatch):
    def boom(cfg):
        raise AssertionError("ensure_server nao deve ser chamado no backend run")
    monkeypatch.setattr(loop_mod, "ensure_server", boom)
    sentinel = object()
    monkeypatch.setattr(loop_mod, "make_client", lambda cfg: sentinel)
    cfg = Config(opencode_bin="/x/o", timeout_s=10, agent_backend="run")
    assert loop_mod.resolve_client(cfg, io.StringIO()) is sentinel


def test_main_text_mode_falls_back_to_run_when_serve_down(monkeypatch):
    monkeypatch.setattr(loop_mod, "ensure_server", lambda cfg: False)
    monkeypatch.setattr(
        loop_mod, "load_config",
        lambda: Config(opencode_bin="/x/o", timeout_s=10, agent_backend="serve"),
    )
    monkeypatch.setattr(
        loop_mod, "RunClient",
        lambda cfg: type("C", (), {"ask": lambda self, t, timeout_s=None: "pong"})(),
    )
    inp, out, err = io.StringIO("Responda apenas: pong\n"), io.StringIO(), io.StringIO()
    monkeypatch.setattr(loop_mod.sys, "stdin", inp)
    monkeypatch.setattr(loop_mod.sys, "stdout", out)
    monkeypatch.setattr(loop_mod.sys, "stderr", err)
    assert main([]) == 0
    assert out.getvalue().strip() == "pong"
    assert "[aviso]" in err.getvalue()


class FakeHub:
    def __init__(self):
        self.states = []

    def set(self, state, detail=None):
        self.states.append(state)

    def take_command(self):
        return None

    def subscribers(self):
        return 1


def test_voice_loop_emits_happy_path_states(monkeypatch):
    hub = FakeHub()
    monkeypatch.setattr("loop.record", lambda **k: "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: "faca algo")
    monkeypatch.setattr("loop.speak", lambda text, **k: None)

    class Client:
        def ask(self, task, timeout_s=None):
            return "resposta"

    voice_loop(client=Client(), iterations=1, record_seconds=1, config=CFG, hub=hub)
    assert hub.states == [
        "idle", "listening", "transcribing", "thinking", "speaking", "idle",
    ]


def test_voice_loop_emits_error_on_agent_failure(monkeypatch):
    from agent_client import AgentError

    hub = FakeHub()
    monkeypatch.setattr("loop.record", lambda **k: "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: "faca algo")
    monkeypatch.setattr("loop.speak", lambda text, **k: None)

    class Client:
        def ask(self, task, timeout_s=None):
            raise AgentError("boom")

    voice_loop(client=Client(), iterations=1, record_seconds=1, config=CFG, hub=hub)
    assert hub.states == [
        "idle", "listening", "transcribing", "thinking", "error", "speaking", "idle",
    ]


def test_voice_loop_vision_failure_emits_error_then_idle(monkeypatch):
    hub = FakeHub()
    monkeypatch.setattr("loop.record", lambda **k: "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: "olha isso")

    def boom(**k):
        raise VoiceError("sem camera")
    monkeypatch.setattr("loop.capture", boom)

    class Client:
        def ask(self, task, timeout_s=None):
            return "resposta"

    voice_loop(client=Client(), iterations=1, record_seconds=1, config=CFG, hub=hub)
    assert "error" in hub.states
    assert hub.states[-1] == "idle"


def test_voice_loop_tts_failure_emits_idle(monkeypatch):
    hub = FakeHub()
    monkeypatch.setattr("loop.record", lambda **k: "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: "faca algo")

    def boom(text, **k):
        raise VoiceError("SAPI indisponivel")
    monkeypatch.setattr("loop.speak", boom)

    class Client:
        def ask(self, task, timeout_s=None):
            return "resposta"

    voice_loop(client=Client(), iterations=1, record_seconds=1, config=CFG, hub=hub)
    assert hub.states[-1] == "idle"


def test_voice_loop_without_hub_still_runs(monkeypatch):
    calls = []
    monkeypatch.setattr("loop.record", lambda **k: "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: "x")
    monkeypatch.setattr("loop.speak", lambda text, **k: None)

    class Client:
        def ask(self, task, timeout_s=None):
            calls.append("ask")
            return "r"

    voice_loop(client=Client(), iterations=1, record_seconds=1, config=CFG)
    assert calls == ["ask"]


def test_voice_loop_tts_abort_ends_error(monkeypatch):
    hub = FakeHub()
    calls = []
    monkeypatch.setattr("loop.record", lambda **k: calls.append("record") or "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: "faca algo")

    def boom(text, **k):
        calls.append("speak")
        raise VoiceError("SAPI indisponivel")
    monkeypatch.setattr("loop.speak", boom)

    class Client:
        def ask(self, task, timeout_s=None):
            calls.append("ask")
            return "resposta"

    voice_loop(client=Client(), iterations=0, record_seconds=1, config=CFG,
               hub=hub, max_consecutive_errors=1, err=io.StringIO())
    assert hub.states[-1] == "error"
    assert calls == ["record", "ask", "speak"]


def test_voice_loop_vision_abort_ends_error(monkeypatch):
    hub = FakeHub()
    calls = []
    monkeypatch.setattr("loop.record", lambda **k: calls.append("record") or "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: calls.append("stt") or "olha isso")

    def boom(**k):
        raise VoiceError("sem camera")
    monkeypatch.setattr("loop.capture", boom)

    class Client:
        def ask(self, task, timeout_s=None):
            calls.append("ask")
            return "resposta"

    voice_loop(client=Client(), iterations=0, record_seconds=1, config=CFG,
               hub=hub, max_consecutive_errors=1, err=io.StringIO())
    assert hub.states[-1] == "error"
    assert calls == ["record", "stt"]


class FakeHubServer:
    def __init__(self, *a, **k):
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


def test_start_hub_starts_and_returns():
    cfg = Config(opencode_bin="/x/o", timeout_s=10, state_port=0)
    hub = loop_mod._start_hub(cfg, io.StringIO())
    try:
        assert hub is not None
        assert hub.subscribers() == 0
    finally:
        hub.stop()


def test_main_starts_and_stops_hub(monkeypatch):
    made = {}
    monkeypatch.setattr(loop_mod, "ensure_server", lambda cfg: True)
    monkeypatch.setattr(loop_mod, "make_client", lambda cfg: "client")

    def make_hub(*a, **k):
        made["hub"] = FakeHubServer()
        return made["hub"]
    monkeypatch.setattr(loop_mod, "StateHub", make_hub)
    seen_hub = {}
    monkeypatch.setattr(loop_mod, "voice_loop",
                        lambda c, **k: seen_hub.update(hub=k.get("hub")))
    assert main(["--voice", "--once", "1"]) == 0
    assert made["hub"].started is True
    assert made["hub"].stopped is True
    assert seen_hub["hub"] is made["hub"]


def test_main_degrades_without_indicator_when_hub_fails(monkeypatch):
    err = io.StringIO()
    def boom(*a, **k):
        raise OSError("porta ocupada")
    monkeypatch.setattr(loop_mod, "StateHub", boom)
    conn = loop_mod._start_hub(load_config({}), err)
    assert conn is None
    assert "[aviso]" in err.getvalue()


class CmdHub:
    def __init__(self, cmds=None, subs=1):
        self.states = []
        self._cmds = list(cmds or [])
        self._subs = subs

    def set(self, state, detail=None):
        self.states.append(state)

    def take_command(self):
        return self._cmds.pop(0) if self._cmds else None

    def subscribers(self):
        return self._subs


class ClientOK:
    def ask(self, task, timeout_s=None):
        return "resposta"


def _patch_voice(monkeypatch, calls):
    monkeypatch.setattr("loop.record", lambda **k: calls.append("record") or "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: calls.append("stt") or "oi")
    monkeypatch.setattr("loop.speak", lambda text, **k: calls.append("tts"))


def test_gui_lost_helper():
    assert loop_mod.gui_lost(False, 0, 0.0, 100.0, 15.0) is False
    assert loop_mod.gui_lost(True, 1, 0.0, 100.0, 15.0) is False
    assert loop_mod.gui_lost(True, 0, 0.0, 10.0, 15.0) is False
    assert loop_mod.gui_lost(True, 0, 0.0, 20.0, 15.0) is True


def test_pause_command_skips_capture(monkeypatch):
    calls = []
    _patch_voice(monkeypatch, calls)
    hub = CmdHub(cmds=["pause"])
    cfg = Config(opencode_bin="/x/o", timeout_s=10, record_seconds=1,
                 input_mode="fixed", ptt=False, state_require_gui=True)
    voice_loop(client=ClientOK(), iterations=1, record_seconds=1, config=cfg, hub=hub)
    assert "record" not in calls


def test_pause_does_not_busy_loop(monkeypatch):
    calls = []
    _patch_voice(monkeypatch, calls)
    sleeps = []
    monkeypatch.setattr("loop.time.sleep", lambda s: sleeps.append(s))
    hub = CmdHub(cmds=["pause"], subs=1)
    cfg = Config(opencode_bin="/x/o", timeout_s=10, record_seconds=1,
                 input_mode="fixed", ptt=False, state_require_gui=False)
    voice_loop(client=ClientOK(), iterations=6, record_seconds=1, config=cfg, hub=hub)
    # idle so na entrada + na transicao para pausa; nao a cada iteracao.
    assert hub.states.count("idle") == 2
    assert len(sleeps) == 6
    assert "record" not in calls


def test_hub_failure_does_not_break_loop(monkeypatch):
    calls = []
    _patch_voice(monkeypatch, calls)

    class BadHub:
        def set(self, state, detail=None):
            raise RuntimeError("hub quebrado")

        def take_command(self):
            raise RuntimeError("hub quebrado")

        def subscribers(self):
            raise RuntimeError("hub quebrado")

    voice_loop(client=ClientOK(), iterations=1, record_seconds=1, config=CFG,
               hub=BadHub())
    assert calls == ["record", "stt", "tts"]


def test_mute_command_skips_tts_but_logs(monkeypatch):
    calls = []
    records = []
    _patch_voice(monkeypatch, calls)
    monkeypatch.setattr("loop.log_turn", lambda rec, config=None: records.append(rec))
    hub = CmdHub(cmds=["mute"])
    voice_loop(client=ClientOK(), iterations=1, record_seconds=1, config=CFG, hub=hub)
    assert "tts" not in calls
    assert len(records) == 1


def test_quit_command_stops_before_capture(monkeypatch):
    calls = []
    _patch_voice(monkeypatch, calls)
    hub = CmdHub(cmds=["quit"])
    voice_loop(client=ClientOK(), iterations=0, record_seconds=1, config=CFG, hub=hub)
    assert "record" not in calls


def test_orphan_exits_when_gui_gone(monkeypatch):
    calls = []
    _patch_voice(monkeypatch, calls)
    hub = CmdHub(subs=0)
    err = io.StringIO()
    cfg = Config(opencode_bin="/x/o", timeout_s=10, record_seconds=1,
                 input_mode="fixed", ptt=False, state_require_gui=True)
    # 1º tick = last_gui_ts (folga); 2º tick já estoura o timeout, antes de capturar.
    ticks = iter([0.0, 100.0, 100.0, 100.0])
    monkeypatch.setattr("loop.time.monotonic", lambda: next(ticks, 100.0))
    voice_loop(client=ClientOK(), iterations=0, record_seconds=1, config=cfg,
               hub=hub, err=err, orphan_timeout_s=15.0)
    assert "record" not in calls
    assert "overlay ausente" in err.getvalue()


def test_orphan_does_not_exit_with_subscriber(monkeypatch):
    calls = []
    _patch_voice(monkeypatch, calls)
    hub = CmdHub(subs=1)
    cfg = Config(opencode_bin="/x/o", timeout_s=10, record_seconds=1,
                 input_mode="fixed", ptt=False, state_require_gui=True)
    voice_loop(client=ClientOK(), iterations=1, record_seconds=1, config=cfg,
               hub=hub, orphan_timeout_s=15.0)
    assert "record" in calls


from agent_client import AgentError


def _stream_cfg(**over):
    base = dict(opencode_bin="/x/o", timeout_s=10, agent_backend="serve",
                input_mode="fixed", ptt=False, stream_tts=True,
                stream_min_chars=5)
    base.update(over)
    return Config(**base)


def test_stream_turn_speaks_chunks_in_order(monkeypatch):
    spoken = []
    monkeypatch.setattr("stream.speak", lambda text, **k: spoken.append(text))

    class StreamClient:
        def stream(self, task, on_delta, on_idle=None, timeout_s=None):
            on_delta("Olá, tudo bem? ")
            on_delta("Como posso ajudar você hoje? ")
            return "Olá, tudo bem? Como posso ajudar você hoje?"

    hub = FakeHub()
    res = loop_mod._stream_turn(StreamClient(), "oi", _stream_cfg(), hub, False,
                                time.monotonic(), io.StringIO())
    assert res.streamed is True
    assert res.spoken == ["Olá, tudo bem?", "Como posso ajudar você hoje?"]
    assert spoken == res.spoken
    assert "speaking" in hub.states


def test_stream_turn_emits_speaking_before_first_audio(monkeypatch):
    hub = FakeHub()
    snapshots = []
    monkeypatch.setattr(
        "stream.speak", lambda text, **k: snapshots.append(list(hub.states))
    )

    class StreamClient:
        def stream(self, task, on_delta, on_idle=None, timeout_s=None):
            on_delta("Uma frase completa. ")
            return "Uma frase completa."

    res = loop_mod._stream_turn(StreamClient(), "oi", _stream_cfg(), hub, False,
                                time.monotonic(), io.StringIO())
    assert res.spoken == ["Uma frase completa."]
    assert snapshots
    assert "speaking" in snapshots[0]


def test_stream_turn_failure_before_speech(monkeypatch):
    class BoomClient:
        def stream(self, *a, **k):
            raise AgentError("sem sse")

    res = loop_mod._stream_turn(BoomClient(), "oi", _stream_cfg(), FakeHub(), False,
                                time.monotonic(), io.StringIO())
    assert res.streamed is False
    assert res.spoken == []
    assert res.failed == "sem sse"


def test_stream_turn_failure_after_speech_keeps_spoken(monkeypatch):
    monkeypatch.setattr("stream.speak", lambda text, **k: None)

    class HalfClient:
        def stream(self, task, on_delta, on_idle=None, timeout_s=None):
            on_delta("Uma frase completa. ")
            raise AgentError("caiu no meio")

    res = loop_mod._stream_turn(HalfClient(), "oi", _stream_cfg(), FakeHub(), False,
                                time.monotonic(), io.StringIO())
    assert res.streamed is False
    assert res.spoken == ["Uma frase completa."]
    assert res.failed == "caiu no meio"


def test_stream_turn_muted_does_not_speak(monkeypatch):
    spoken = []
    monkeypatch.setattr("stream.speak", lambda text, **k: spoken.append(text))

    class StreamClient:
        def stream(self, task, on_delta, on_idle=None, timeout_s=None):
            on_delta("Uma resposta qualquer. ")
            return "Uma resposta qualquer."

    hub = FakeHub()
    res = loop_mod._stream_turn(StreamClient(), "oi", _stream_cfg(), hub, True,
                                time.monotonic(), io.StringIO())
    assert res.answer == "Uma resposta qualquer."
    assert spoken == []
    assert "speaking" not in hub.states


def test_voice_loop_falls_back_to_ask_when_stream_fails(monkeypatch):
    calls = []
    monkeypatch.setattr("loop.record", lambda **k: "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: "oi")
    monkeypatch.setattr("loop.speak", lambda text, **k: calls.append(text))

    class BoomClient:
        def stream(self, *a, **k):
            raise AgentError("sem sse")

        def ask(self, task, timeout_s=None):
            return "resposta bloqueante"

    voice_loop(client=BoomClient(), iterations=1, record_seconds=1,
               config=_stream_cfg(), hub=FakeHub())
    assert calls == ["resposta bloqueante"]


def test_voice_loop_streams_without_calling_ask(monkeypatch):
    asked = []
    spoken = []
    monkeypatch.setattr("loop.record", lambda **k: "/tmp/a.wav")
    monkeypatch.setattr("loop.transcribe", lambda wav, **k: "oi")
    monkeypatch.setattr("stream.speak", lambda text, **k: spoken.append(text))

    class StreamClient:
        def stream(self, task, on_delta, on_idle=None, timeout_s=None):
            on_delta("Resposta em streaming. ")
            return "Resposta em streaming."

        def ask(self, *a, **k):
            asked.append(True)
            return "x"

    hub = FakeHub()
    voice_loop(client=StreamClient(), iterations=1, record_seconds=1,
               config=_stream_cfg(), hub=hub)
    assert asked == []
    assert spoken == ["Resposta em streaming."]
    assert "speaking" in hub.states

