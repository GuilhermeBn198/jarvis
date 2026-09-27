import json
import subprocess
import urllib.request

from config import Config


class AgentError(RuntimeError):
    pass


class RunClient:
    def __init__(self, config: Config, cwd: str | None = None):
        self._cfg = config
        self._cwd = cwd

    def ask(self, task: str, timeout_s: int | None = None) -> str:
        task = (task or "").strip()
        if not task:
            raise AgentError("tarefa vazia")
        timeout = timeout_s if timeout_s is not None else self._cfg.timeout_s
        try:
            proc = subprocess.run(
                [self._cfg.opencode_bin, "run", "--pure", task],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self._cwd,
            )
        except FileNotFoundError as exc:
            raise AgentError(
                f"opencode nao encontrado em {self._cfg.opencode_bin} (defina OPENCODE_BIN)"
            ) from exc
        except PermissionError as exc:
            raise AgentError(f"opencode em {self._cfg.opencode_bin} nao e executavel") from exc
        except OSError as exc:
            raise AgentError(f"falha ao executar opencode ({exc})") from exc
        except subprocess.TimeoutExpired as exc:
            raise AgentError(f"timeout ({timeout}s) ao chamar o agente") from exc
        if proc.returncode != 0:
            raise AgentError(f"opencode falhou ({proc.returncode}): {proc.stderr.strip()[:200]}")
        if not proc.stdout.strip():
            raise AgentError("agente nao retornou resposta")
        return proc.stdout.strip()


class ServeClient:
    def __init__(self, config: Config):
        self._cfg = config
        self._session_id: str | None = None

    def _post(self, path: str, payload: dict, timeout: int) -> dict:
        url = self._cfg.server_url.rstrip("/") + path
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
        except (OSError, ValueError) as exc:
            raise AgentError(f"falha ao falar com o servidor em {url} ({exc})") from exc
        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise AgentError(f"resposta invalida do servidor ({exc})") from exc

    def _ensure_session(self, timeout: int) -> str:
        if self._session_id:
            return self._session_id
        data = self._post("/session", {}, timeout)
        session_id = data.get("id")
        if not session_id:
            raise AgentError("servidor nao retornou id de sessao")
        self._session_id = session_id
        return session_id

    def ask(self, task: str, timeout_s: int | None = None) -> str:
        task = (task or "").strip()
        if not task:
            raise AgentError("tarefa vazia")
        timeout = timeout_s if timeout_s is not None else self._cfg.timeout_s
        session_id = self._ensure_session(timeout)
        data = self._post(
            f"/session/{session_id}/message",
            {"parts": [{"type": "text", "text": task}]},
            timeout,
        )
        parts = data.get("parts") or []
        text = "".join(
            p.get("text", "") for p in parts if p.get("type") == "text"
        ).strip()
        if not text:
            raise AgentError("agente nao retornou resposta")
        return text


def make_client(cfg: Config):
    if cfg.agent_backend == "serve":
        return ServeClient(cfg)
    return RunClient(cfg)
