import json
import queue
import threading
import time

STATES = ("idle", "listening", "transcribing", "thinking", "speaking", "acting", "error")
COMMANDS = ("mute", "pause", "quit")
HEARTBEAT_S = 10.0


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
