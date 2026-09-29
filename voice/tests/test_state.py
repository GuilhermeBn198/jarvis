import queue
import urllib.error

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


import json
import time
import urllib.request


def _read_line(resp):
    return resp.readline().decode("utf-8")


def test_http_state_endpoint():
    hub = StateHub(port=0)
    hub.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{hub._port}/state", timeout=2) as r:
            assert r.status == 200
            assert json.loads(r.read())["state"] == "idle"
        hub.set("acting")
        with urllib.request.urlopen(f"http://127.0.0.1:{hub._port}/state", timeout=2) as r:
            assert json.loads(r.read())["state"] == "acting"
    finally:
        hub.stop()


def test_events_sends_snapshot_then_transitions():
    hub = StateHub(port=0)
    hub.start()
    try:
        resp = urllib.request.urlopen(
            f"http://127.0.0.1:{hub._port}/events", timeout=3
        )
        first = _read_line(resp)
        assert first.startswith("data: ")
        assert json.loads(first[6:])["state"] == "idle"
        assert _read_line(resp) == "\n"
        hub.set("listening")
        second = _read_line(resp)
        assert json.loads(second[6:])["state"] == "listening"
        resp.close()
        hub.stop()
        time.sleep(0.05)
        assert hub.subscribers() == 0
    finally:
        hub.stop()


def test_post_command_enqueues_and_validates():
    hub = StateHub(port=0)
    hub.start()
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{hub._port}/command",
            data=json.dumps({"cmd": "mute"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=2) as r:
            assert r.status == 200
        assert hub.take_command() == "mute"

        bad = urllib.request.Request(
            f"http://127.0.0.1:{hub._port}/command",
            data=json.dumps({"cmd": "explode"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(bad, timeout=2)
            assert False, "deveria dar 400"
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
    finally:
        hub.stop()


def test_start_stop_is_clean():
    hub = StateHub(port=0)
    hub.start()
    hub.start()  # idempotente
    hub.stop()
    hub.stop()  # idempotente
