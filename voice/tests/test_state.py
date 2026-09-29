import queue

import pytest

from state import COMMANDS, STATES, StateHub


def test_set_publishes_to_subscriber():
    hub = StateHub(port=0)
    q = hub.subscribe()
    hub.set("thinking", "agente")
    payload = q.get_nowait()
    assert '"state": "thinking"' in payload
    assert '"detail": "agente"' in payload


def test_snapshot_reflects_last_state():
    hub = StateHub(port=0)
    assert hub.snapshot()["state"] == "idle"
    hub.set("speaking")
    snap = hub.snapshot()
    assert snap["state"] == "speaking"
    assert "ts" in snap


def test_set_rejects_unknown_state():
    hub = StateHub(port=0)
    with pytest.raises(ValueError):
        hub.set("dormindo")


def test_subscribers_count_and_unsubscribe():
    hub = StateHub(port=0)
    q = hub.subscribe()
    assert hub.subscribers() == 1
    hub.unsubscribe(q)
    assert hub.subscribers() == 0
    hub.unsubscribe(q)  # idempotente
    assert hub.subscribers() == 0


def test_take_command_empty_is_none():
    hub = StateHub(port=0)
    assert hub.take_command() is None


def test_push_and_take_command_fifo():
    hub = StateHub(port=0)
    hub.push_command("mute")
    hub.push_command("quit")
    assert hub.take_command() == "mute"
    assert hub.take_command() == "quit"
    assert hub.take_command() is None


def test_push_command_rejects_unknown():
    hub = StateHub(port=0)
    with pytest.raises(ValueError):
        hub.push_command("explode")


def test_states_and_commands_are_exact():
    assert STATES == (
        "idle", "listening", "transcribing", "thinking",
        "speaking", "acting", "error",
    )
    assert COMMANDS == ("mute", "pause", "quit")
