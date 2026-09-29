import json
import queue
import select
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SSE_POLL_S = 0.1

STATES = ("idle", "listening", "transcribing", "thinking", "speaking", "acting", "error")
COMMANDS = ("mute", "pause", "quit")
HEARTBEAT_S = 10.0


def _make_handler(hub):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _json(self, code: int, obj: dict) -> None:
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_GET(self):
            if self.path == "/state":
                self._json(200, hub.snapshot())
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
            self.send_header("Access-Control-Allow-Origin", "*")
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

        def do_POST(self):
            if self.path != "/command":
                self._json(404, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                cmd = json.loads(raw.decode("utf-8")).get("cmd")
            except (ValueError, UnicodeDecodeError):
                self._json(400, {"error": "json invalido"})
                return
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
        self._subscribers: list[queue.Queue] = []
        self._commands: queue.Queue = queue.Queue()
        self._server = None
        self._thread: threading.Thread | None = None

    def snapshot(self) -> dict:
        with self._lock:
            return {"state": self._state, "detail": self._detail, "ts": time.time()}

    def set(self, state: str, detail: str | None = None) -> None:
        if state not in STATES:
            raise ValueError(f"estado invalido: {state}")
        with self._lock:
            self._state = state
            self._detail = detail
            subs = list(self._subscribers)
        payload = json.dumps({"state": state, "detail": detail, "ts": time.time()})
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
