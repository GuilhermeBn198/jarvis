import json
import os
import subprocess
import time
import urllib.request

from config import Config, serve_port

HEALTH_TIMEOUT_S = 2
POLL_INTERVAL_S = 0.5
DEFAULT_LOG_PATH = "/tmp/opencode/serve.log"


def is_healthy(server_url: str, timeout: int = HEALTH_TIMEOUT_S) -> bool:
    url = server_url.rstrip("/") + "/global/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and data.get("healthy") is True


def _spawn(cfg: Config) -> bool:
    port = serve_port(cfg.server_url)
    log_path = os.environ.get("SERVE_LOG", DEFAULT_LOG_PATH)
    sink = subprocess.DEVNULL
    try:
        d = os.path.dirname(log_path)
        if d:
            os.makedirs(d, exist_ok=True)
        sink = open(log_path, "ab")
    except OSError:
        sink = subprocess.DEVNULL
    try:
        subprocess.Popen(
            [cfg.opencode_bin, "serve", "--port", str(port)],
            stdin=subprocess.DEVNULL,
            stdout=sink,
            stderr=sink,
            cwd=cfg.project_root,
            start_new_session=True,
        )
        return True
    except OSError:
        return False
    finally:
        if sink != subprocess.DEVNULL:
            sink.close()


def ensure_server(config: Config, wait_s: float = 20) -> bool:
    try:
        if is_healthy(config.server_url):
            return True
        if not _spawn(config):
            return False
        deadline = time.monotonic() + wait_s
        while time.monotonic() < deadline:
            if is_healthy(config.server_url):
                return True
            time.sleep(POLL_INTERVAL_S)
        return False
    except Exception:
        return False
