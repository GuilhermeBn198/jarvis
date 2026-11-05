import json
import queue
import select
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from settings import load_settings, save_settings
from model_selection import list_ollama_models, select_ollama_model

SSE_POLL_S = 0.1

STATES = ("idle", "listening", "transcribing", "thinking", "speaking", "acting", "error")
COMMANDS = ("mute", "pause", "quit", "measure")
HEARTBEAT_S = 10.0
TRUSTED_UI_ORIGINS = frozenset({
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
})


def _make_handler(hub):
    class Handler(BaseHTTPRequestHandler):
        # SSE precisa de HTTP/1.1: o EventSource do Chromium/WebView2 rejeita
        # uma resposta HTTP/1.0 com `Connection: keep-alive` (o curl aceita,
        # mas o webview nao entrega os eventos).
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def _trusted_origin(self) -> str | None:
            origin = self.headers.get("Origin")
            return origin if origin in TRUSTED_UI_ORIGINS else None

        def _reject_untrusted_origin(self, *, required: bool = False) -> bool:
            origin = self.headers.get("Origin")
            if origin in TRUSTED_UI_ORIGINS or (origin is None and not required):
                return False
            self._json(403, {"error": "origin not allowed"})
            return True

        def _add_cors_headers(self) -> None:
            origin = self._trusted_origin()
            if origin is not None:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")

        def _json(self, code: int, obj: dict) -> None:
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self._add_cors_headers()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            if self._trusted_origin() is None:
                self.send_response(403)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(204)
            self._add_cors_headers()
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_GET(self):
            if self._reject_untrusted_origin():
                return
            if self.path == "/state":
                self._json(200, hub.snapshot())
            elif self.path == "/settings":
                self._json(200, load_settings())
            elif self.path == "/models":
                try:
                    self._json(200, {"models": list_ollama_models(), "selected": load_settings().get("agent_model")})
                except (RuntimeError, ValueError) as exc:
                    self._json(503, {"error": str(exc), "selected": load_settings().get("agent_model")})
            elif self.path == "/mic-level":
                result = hub.measure_result()
                self._json(200, result if result is not None else {"pending": True})
            elif self.path == "/devices":
                try:
                    from capture import list_audio_devices
                    from config import load_config

                    self._json(200, {
                        "devices": list_audio_devices(),
                        "current": load_config().mic_device,
                    })
                except Exception as exc:  # fronteira HTTP: nunca derruba o hub
                    self._json(200, {"devices": [], "current": None, "error": str(exc)})
            elif self.path == "/events":
                self._events()
            else:
                self._json(404, {"error": "not found"})

        def _peer_closed(self) -> bool:
            try:
                readable, _, _ = select.select([self.connection], [], [], 0)
            except (OSError, ValueError):
                return True
            if not readable:
                return False
            try:
                return self.connection.recv(1, socket.MSG_PEEK) == b""
            except (ConnectionResetError, OSError):
                return True

        def _events(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self._add_cors_headers()
            self.end_headers()
            q = hub.subscribe()
            last_ping = time.monotonic()
            try:
                self.wfile.write(
                    f"data: {json.dumps(hub.snapshot())}\n\n".encode("utf-8")
                )
                self.wfile.flush()
                while True:
                    try:
                        payload = q.get(timeout=SSE_POLL_S)
                        self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                        self.wfile.flush()
                    except queue.Empty:
                        if self._peer_closed():
                            break
                        if time.monotonic() - last_ping >= HEARTBEAT_S:
                            self.wfile.write(b": ping\n\n")
                            self.wfile.flush()
                            last_ping = time.monotonic()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                hub.unsubscribe(q)

        def _read_json(self):
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                obj = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return None
            return obj if isinstance(obj, dict) else None

        def do_POST(self):
            if self._reject_untrusted_origin(required=True):
                return
            if self.path == "/settings":
                obj = self._read_json()
                if obj is None:
                    self._json(400, {"error": "json invalido"})
                    return
                obj.pop("agent_model", None)  # modelo exige validacao contra o catalogo ao vivo.
                self._json(200, save_settings(obj))
                return
            if self.path == "/model":
                obj = self._read_json()
                if obj is None:
                    self._json(400, {"error": "json invalido"})
                    return
                try:
                    self._json(200, select_ollama_model(obj.get("model")))
                except ValueError as exc:
                    self._json(400, {"error": str(exc), "selected": load_settings().get("agent_model")})
                except RuntimeError as exc:
                    self._json(503, {"error": str(exc), "selected": load_settings().get("agent_model")})
                return
            if self.path != "/command":
                self._json(404, {"error": "not found"})
                return
            obj = self._read_json()
            if obj is None:
                self._json(400, {"error": "json invalido"})
                return
            cmd = obj.get("cmd")
            if cmd not in COMMANDS:
                self._json(400, {"error": f"comando invalido: {cmd}"})
                return
            hub.push_command(cmd)
            self._json(200, {"ok": True})

    return Handler


class StateHub:
    def __init__(self, port: int = 8765, host: str = "127.0.0.1"):
        self._host = host
        self._port = port
        self._lock = threading.Lock()
        self._state = "idle"
        self._detail: str | None = None
        self._muted = False
        self._paused = False
        self._level = 0.0
        self._subscribers: list[queue.Queue] = []
        self._commands: queue.Queue = queue.Queue()
        self._measure_result: dict | None = None
        self._server = None
        self._thread: threading.Thread | None = None

    def _payload(self) -> dict:
        # Chamado com o lock ja adquirido.
        return {
            "state": self._state,
            "detail": self._detail,
            "muted": self._muted,
            "paused": self._paused,
            "level": self._level,
            "ts": time.time(),
        }

    def snapshot(self) -> dict:
        with self._lock:
            return self._payload()

    def set(self, state: str, detail: str | None = None) -> None:
        if state not in STATES:
            raise ValueError(f"estado invalido: {state}")
        with self._lock:
            self._state = state
            self._detail = detail
            subs = list(self._subscribers)
            payload = json.dumps(self._payload())
        for q in subs:
            q.put(payload)

    def set_flags(self, muted: bool | None = None, paused: bool | None = None) -> None:
        with self._lock:
            if muted is not None:
                self._muted = bool(muted)
            if paused is not None:
                self._paused = bool(paused)
            subs = list(self._subscribers)
            payload = json.dumps(self._payload())
        for q in subs:
            q.put(payload)

    def set_level(self, level: float) -> None:
        """Publica o nivel de audio (0..1) para o orbe reagir ao vivo (v2).

        So notifica assinantes se o valor mudou o suficiente (evita flood de SSE
        durante a captura, que atualiza varias vezes por segundo).
        """
        try:
            v = float(level)
        except (TypeError, ValueError):
            return
        v = max(0.0, min(1.0, v))
        with self._lock:
            if abs(v - self._level) < 0.02:
                return
            self._level = v
            subs = list(self._subscribers)
            payload = json.dumps(self._payload())
        for q in subs:
            q.put(payload)

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def subscribers(self) -> int:
        with self._lock:
            return len(self._subscribers)

    def take_command(self) -> str | None:
        try:
            return self._commands.get_nowait()
        except queue.Empty:
            return None

    def push_command(self, cmd: str) -> None:
        if cmd not in COMMANDS:
            raise ValueError(f"comando invalido: {cmd}")
        self._commands.put(cmd)

    def set_measure_result(self, result: dict) -> None:
        with self._lock:
            self._measure_result = result

    def measure_result(self) -> dict | None:
        with self._lock:
            return self._measure_result

    def start(self) -> None:
        if self._server is not None:
            return
        server = ThreadingHTTPServer((self._host, self._port), _make_handler(self))
        server.daemon_threads = True
        self._port = server.server_address[1]
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
