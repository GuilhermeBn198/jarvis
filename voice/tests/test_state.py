import http.client
import json
import time
import urllib.error
import urllib.request

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
        "idle",
        "listening",
        "transcribing",
        "thinking",
        "speaking",
        "acting",
        "error",
    )
    assert COMMANDS == ("mute", "pause", "quit", "measure")


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
        resp = urllib.request.urlopen(f"http://127.0.0.1:{hub._port}/events", timeout=3)
        first = _read_line(resp)
        assert first.startswith("data: ")
        assert json.loads(first[6:])["state"] == "idle"
        assert _read_line(resp) == "\n"
        hub.set("listening")
        second = _read_line(resp)
        assert json.loads(second[6:])["state"] == "listening"
        resp.close()
        hub.stop()
        deadline = time.monotonic() + 1.0
        while hub.subscribers() != 0 and time.monotonic() < deadline:
            time.sleep(0.05)
        assert hub.subscribers() == 0
    finally:
        hub.stop()


def test_cors_headers_on_state_and_events():
    hub = StateHub(port=0)
    hub.start()
    try:
        with urllib.request.urlopen(
            urllib.request.Request(
                f"http://127.0.0.1:{hub._port}/state",
                headers={"Origin": "tauri://localhost"},
            ),
            timeout=2,
        ) as r:
            assert r.headers["Access-Control-Allow-Origin"] == "tauri://localhost"
            assert r.headers["Vary"] == "Origin"
        resp = urllib.request.urlopen(
            urllib.request.Request(
                f"http://127.0.0.1:{hub._port}/events",
                headers={"Origin": "tauri://localhost"},
            ),
            timeout=3,
        )
        try:
            assert resp.headers["Access-Control-Allow-Origin"] == "tauri://localhost"
            assert resp.headers["Vary"] == "Origin"
        finally:
            resp.close()
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(
                urllib.request.Request(
                    f"http://127.0.0.1:{hub._port}/settings",
                    headers={"Origin": "https://attacker.example"},
                ),
                timeout=2,
            )
        assert error.value.code == 403
        assert "Access-Control-Allow-Origin" not in error.value.headers
    finally:
        hub.stop()


@pytest.mark.parametrize("origin", ["http://tauri.localhost", "https://tauri.localhost"])
def test_windows_tauri_origin_remains_trusted(origin):
    hub = StateHub(port=0)
    hub.start()
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{hub._port}/state",
            headers={"Origin": origin},
        )
        with urllib.request.urlopen(req, timeout=2) as response:
            assert response.status == 200
            assert response.headers["Access-Control-Allow-Origin"] == origin
    finally:
        hub.stop()


def test_options_preflight_allows_trusted_tauri_origin():
    hub = StateHub(port=0)
    hub.start()
    try:
        resp = urllib.request.urlopen(
            urllib.request.Request(
                f"http://127.0.0.1:{hub._port}/command",
                method="OPTIONS",
                headers={
                    "Origin": "tauri://localhost",
                    "Access-Control-Request-Method": "POST",
                },
            ),
            timeout=2,
        )
        try:
            assert resp.status == 204
            assert resp.headers["Access-Control-Allow-Origin"] == "tauri://localhost"
            assert "POST" in resp.headers["Access-Control-Allow-Methods"]
            assert "Content-Type" in resp.headers["Access-Control-Allow-Headers"]
        finally:
            resp.close()
    finally:
        hub.stop()


def test_options_preflight_rejects_untrusted_origin():
    hub = StateHub(port=0)
    hub.start()
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{hub._port}/model",
            method="OPTIONS",
            headers={
                "Origin": "https://attacker.example",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(req, timeout=2)
        assert error.value.code == 403
    finally:
        hub.stop()


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/model", {"model": "ollama/minimax-m3.1-flash:cloud"}),
        ("/settings", {"theme": "dark"}),
        ("/command", {"cmd": "quit"}),
    ],
)
@pytest.mark.parametrize("origin", ["https://attacker.example", None])
def test_post_rejects_untrusted_or_missing_origin_without_side_effects(path, payload, origin, tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_SETTINGS", str(tmp_path / "s.json"))
    settings_path = tmp_path / "s.json"
    settings_path.write_text(json.dumps({"agent_model": "ollama/local-model"}))
    import state
    monkeypatch.setattr(
        state,
        "list_ollama_models",
        lambda: [
            {"name": "local-model", "cloud": False},
            {"name": "minimax-m3.1-flash:cloud", "cloud": True},
        ],
    )
    hub = StateHub(port=0)
    hub.start()
    try:
        headers = {"Content-Type": "application/json"}
        if origin is not None:
            headers["Origin"] = origin
        req = urllib.request.Request(
            f"http://127.0.0.1:{hub._port}{path}",
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(req, timeout=2)
        assert error.value.code == 403
        assert json.loads(settings_path.read_text()) == {"agent_model": "ollama/local-model"}
        assert hub.take_command() is None
    finally:
        hub.stop()


def test_post_command_enqueues_and_validates():
    hub = StateHub(port=0)
    hub.start()
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{hub._port}/command",
            data=json.dumps({"cmd": "mute"}).encode("utf-8"),
            headers={"Content-Type": "application/json", "Origin": "tauri://localhost"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=2) as r:
            assert r.status == 200
        assert hub.take_command() == "mute"

        bad = urllib.request.Request(
            f"http://127.0.0.1:{hub._port}/command",
            data=json.dumps({"cmd": "explode"}).encode("utf-8"),
            headers={"Content-Type": "application/json", "Origin": "tauri://localhost"},
            method="POST",
        )
        try:
            urllib.request.urlopen(bad, timeout=2)
            assert False, "deveria dar 400"  # noqa: B011
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


def test_server_uses_http_1_1():
    # SSE exige HTTP/1.1: o EventSource do WebView2 rejeita HTTP/1.0 com
    # `Connection: keep-alive` (ver notes/jarvis-state-indicator.md).
    hub = StateHub(port=0)
    hub.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", hub._port, timeout=2)
        conn.request("GET", "/state")
        resp = conn.getresponse()
        assert resp.version == 11
        resp.read()
        conn.close()
    finally:
        hub.stop()


def test_measure_is_a_valid_command():
    hub = StateHub(port=0)
    hub.push_command("measure")
    assert hub.take_command() == "measure"
    assert hub.measure_result() is None


def test_get_settings_endpoint_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_SETTINGS", str(tmp_path / "s.json"))
    hub = StateHub(port=0)
    hub.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{hub._port}/settings", timeout=2) as r:
            assert json.loads(r.read()) == {}
    finally:
        hub.stop()


def test_models_endpoint_returns_ollama_catalog_and_selected(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_SETTINGS", str(tmp_path / "s.json"))
    import state
    monkeypatch.setattr(state, "list_ollama_models", lambda: [{"name":"minimax-m3.1-flash:cloud","cloud":True}])
    monkeypatch.setattr(state, "load_settings", lambda: {"agent_model":"ollama/minimax-m3.1-flash:cloud"})
    hub = StateHub(port=0)
    hub.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{hub._port}/models", timeout=2) as r:
            assert json.loads(r.read()) == {"models":[{"name":"minimax-m3.1-flash:cloud","cloud":True}],"selected":"ollama/minimax-m3.1-flash:cloud"}
    finally:
        hub.stop()


def test_post_model_endpoint_validates_catalog_and_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_SETTINGS", str(tmp_path / "s.json"))
    import state
    monkeypatch.setattr(state, "list_ollama_models", lambda: [{"name":"minimax-m3.1-flash:cloud","cloud":True}])
    hub = StateHub(port=0)
    hub.start()
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{hub._port}/model", data=json.dumps({"model":"ollama/minimax-m3.1-flash:cloud"}).encode(), headers={"Content-Type":"application/json", "Origin":"tauri://localhost"}, method="POST")
        with urllib.request.urlopen(req, timeout=2) as r:
            assert json.loads(r.read()) == {"selected":"ollama/minimax-m3.1-flash:cloud","cloud":True}
        assert json.loads((tmp_path / "s.json").read_text())["agent_model"] == "ollama/minimax-m3.1-flash:cloud"
        invalid = urllib.request.Request(f"http://127.0.0.1:{hub._port}/model", data=json.dumps({"model":"ollama/unknown"}).encode(), headers={"Content-Type":"application/json", "Origin":"tauri://localhost"}, method="POST")
        try:
            urllib.request.urlopen(invalid, timeout=2)
            assert False, "expected HTTP 400"
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
        assert json.loads((tmp_path / "s.json").read_text())["agent_model"] == "ollama/minimax-m3.1-flash:cloud"
    finally:
        hub.stop()


def test_post_settings_endpoint_persists(tmp_path, monkeypatch):
    p = tmp_path / "s.json"
    monkeypatch.setenv("JARVIS_SETTINGS", str(p))
    hub = StateHub(port=0)
    hub.start()
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{hub._port}/settings",
            data=json.dumps({"noise_db": -28}).encode("utf-8"),
            headers={"Content-Type": "application/json", "Origin": "tauri://localhost"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=2) as r:
            assert json.loads(r.read())["noise_db"] == -28
        assert json.loads(p.read_text(encoding="utf-8"))["noise_db"] == -28
    finally:
        hub.stop()


def test_settings_endpoint_cannot_bypass_model_catalog_validation(tmp_path, monkeypatch):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"agent_model":"ollama/old:cloud"}))
    monkeypatch.setenv("JARVIS_SETTINGS", str(p))
    hub = StateHub(port=0)
    hub.start()
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{hub._port}/settings", data=json.dumps({"agent_model":"ollama/arbitrary"}).encode(), headers={"Content-Type":"application/json", "Origin":"tauri://localhost"}, method="POST")
        with urllib.request.urlopen(req, timeout=2) as r:
            assert json.loads(r.read())["agent_model"] == "ollama/old:cloud"
        assert json.loads(p.read_text())["agent_model"] == "ollama/old:cloud"
    finally:
        hub.stop()


def test_mic_level_endpoint_pending_then_result():
    hub = StateHub(port=0)
    hub.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{hub._port}/mic-level", timeout=2) as r:
            assert json.loads(r.read()) == {"pending": True}
        hub.set_measure_result({"mean_db": -40.0, "ok": True})
        with urllib.request.urlopen(f"http://127.0.0.1:{hub._port}/mic-level", timeout=2) as r:
            assert json.loads(r.read())["mean_db"] == -40.0
    finally:
        hub.stop()


def test_devices_endpoint_lists(monkeypatch):
    import capture

    monkeypatch.setattr(capture, "list_audio_devices", lambda config=None: ["Mic A", "Mic B"])
    hub = StateHub(port=0)
    hub.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{hub._port}/devices", timeout=2) as r:
            body = json.loads(r.read())
            assert body["devices"] == ["Mic A", "Mic B"]
            assert "current" in body
    finally:
        hub.stop()


def test_devices_endpoint_error_is_safe(monkeypatch):
    import capture

    def boom(config=None):
        raise RuntimeError("sem ffmpeg")

    monkeypatch.setattr(capture, "list_audio_devices", boom)
    hub = StateHub(port=0)
    hub.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{hub._port}/devices", timeout=2) as r:
            body = json.loads(r.read())
            assert body["devices"] == []
            assert "sem ffmpeg" in body["error"]
    finally:
        hub.stop()


def test_snapshot_includes_flags_and_set_flags_broadcasts():
    hub = StateHub(port=0)
    q = hub.subscribe()
    assert hub.snapshot()["muted"] is False
    assert hub.snapshot()["paused"] is False
    hub.set_flags(muted=True, paused=True)
    payload = json.loads(q.get_nowait())
    assert payload["muted"] is True
    assert payload["paused"] is True
    assert hub.snapshot()["paused"] is True


def test_set_keeps_flags_in_payload():
    hub = StateHub(port=0)
    hub.set_flags(muted=True)
    q = hub.subscribe()
    hub.set("speaking")
    payload = json.loads(q.get_nowait())
    assert payload["state"] == "speaking"
    assert payload["muted"] is True


def test_level_default_e_publicado_no_snapshot():
    hub = StateHub(port=0)
    assert hub.snapshot()["level"] == 0.0
    hub.set_level(0.42)
    assert hub.snapshot()["level"] == 0.42


def test_level_e_clampado_entre_0_e_1():
    hub = StateHub(port=0)
    hub.set_level(5)
    assert hub.snapshot()["level"] == 1.0
    hub.set_level(-3)
    assert hub.snapshot()["level"] == 0.0


def test_set_level_publica_para_subscriber():
    hub = StateHub(port=0)
    q = hub.subscribe()
    hub.set_level(0.7)
    payload = q.get_nowait()
    assert '"level": 0.7' in payload
