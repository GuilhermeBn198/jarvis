import base64
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request

from config import Config
from sanitize import drop_leading_tui, strip_ansi

SESSION_TIMEOUT_S = 10


def _model_payload(model_id: str) -> dict:
    """Converte 'provider/model' no objeto `model` da API do serve."""
    provider, sep, model = model_id.partition("/")
    if not sep or not provider or not model:
        raise AgentError(
            f"model_id invalido (esperado 'provider/model'): {model_id}"
        )
    return {"providerID": provider, "modelID": model}


def strip_opencode_noise(text: str) -> str:
    """Remove ANSI e o cabecalho do TUI (`> build · model`) da saida do opencode."""
    return drop_leading_tui(strip_ansi(text))


class AgentError(RuntimeError):
    pass


class _SessionGone(AgentError):
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
        cmd = [self._cfg.opencode_bin, "run"]
        if self._cfg.agent:
            cmd += ["--agent", self._cfg.agent]
        # `--pure` desabilita os plugins do projeto (incl. o SafetyGate e as
        # tools act_*). So e seguro com um agente SEM tools (ex.: `chat`), que
        # e o default da voz; assim o custo de carregar plugins e evitado sem
        # abrir um buraco de execucao. NUNCA use `--pure` com agente com tools.
        cmd += ["--pure", task]
        try:
            proc = subprocess.run(
                cmd,
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
        cleaned = strip_opencode_noise(proc.stdout)
        if not cleaned.strip():
            raise AgentError("agente nao retornou resposta")
        return cleaned.strip()


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
        except urllib.error.HTTPError as exc:
            if exc.code in (404, 410):
                raise _SessionGone(
                    f"sessao expirada no servidor (HTTP {exc.code})"
                ) from exc
            raise AgentError(
                f"falha ao falar com o servidor em {url} ({exc})"
            ) from exc
        except (OSError, ValueError) as exc:
            raise AgentError(f"falha ao falar com o servidor em {url} ({exc})") from exc
        try:
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise AgentError(f"resposta invalida do servidor ({exc})") from exc
        if not isinstance(data, dict):
            raise AgentError("resposta invalida do servidor (esperado objeto JSON)")
        return data

    def _ensure_session(self, timeout: int) -> str:
        if self._session_id:
            return self._session_id
        data = self._post("/session", {}, min(timeout, SESSION_TIMEOUT_S))
        session_id = data.get("id")
        if not session_id:
            raise AgentError("servidor nao retornou id de sessao")
        self._session_id = session_id
        return session_id

    @staticmethod
    def _extract_reply(data: dict) -> str:
        parts = data.get("parts") or []
        text = "".join(
            p.get("text", "") for p in parts if p.get("type") == "text"
        ).strip()
        if not text:
            raise AgentError("agente nao retornou resposta")
        return text

    def _request_reply(self, session_id: str, task: str, timeout: int) -> str:
        payload = {"parts": [{"type": "text", "text": task}]}
        if self._cfg.agent:
            payload["agent"] = self._cfg.agent
        data = self._post(
            f"/session/{session_id}/message",
            payload,
            timeout,
        )
        return self._extract_reply(data)

    def see(
        self,
        prompt: str,
        png_path: str,
        model_id: str | None = None,
        agent: str = "chat",
    ) -> str:
        """Manda uma imagem (PNG) + prompt para o agente via serve.

        Reaproveita a sessao lazy e envia a imagem como `FilePartInput`
        (data URL base64). Sem o startup do `opencode run` a visao cai de
        ~29s para ~6.5s (ver .superpowers/sdd/latency-opt-report.md).

        O agente e SEMPRE o tool-less `chat`: o conteudo da tela e
        nao-conflavel e nunca pode rodar tools/plugins (SafetyGate, act_*).
        Nao usar `cfg.agent` (que pode estar vazio e cair no default do
        servidor, possivelmente COM tools).
        """
        prompt = (prompt or "").strip()
        if not prompt:
            raise AgentError("prompt vazio")
        try:
            with open(png_path, "rb") as fh:
                raw = fh.read()
        except OSError as exc:
            raise AgentError(f"falha ao ler a imagem {png_path} ({exc})") from exc
        if not raw:
            raise AgentError(f"imagem vazia: {png_path}")
        b64 = base64.b64encode(raw).decode("ascii")
        payload = {
            "parts": [
                {"type": "text", "text": prompt},
                {
                    "type": "file",
                    "mime": "image/png",
                    "filename": os.path.basename(png_path) or "shot.png",
                    "url": "data:image/png;base64," + b64,
                },
            ],
        }
        if model_id:
            payload["model"] = _model_payload(model_id)
        if agent:
            payload["agent"] = agent
        timeout = self._cfg.timeout_s
        session_id = self._ensure_session(timeout)
        try:
            data = self._post(f"/session/{session_id}/message", payload, timeout)
        except _SessionGone:
            self._session_id = None
            session_id = self._ensure_session(timeout)
            data = self._post(f"/session/{session_id}/message", payload, timeout)
        return self._extract_reply(data)

    def ask(self, task: str, timeout_s: int | None = None) -> str:
        task = (task or "").strip()
        if not task:
            raise AgentError("tarefa vazia")
        timeout = timeout_s if timeout_s is not None else self._cfg.timeout_s
        session_id = self._ensure_session(timeout)
        try:
            return self._request_reply(session_id, task, timeout)
        except _SessionGone:
            self._session_id = None
            session_id = self._ensure_session(timeout)
            return self._request_reply(session_id, task, timeout)

    def _post_no_content(self, path: str, payload: dict, timeout: int) -> None:
        url = self._cfg.server_url.rstrip("/") + path
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (404, 410):
                raise _SessionGone(
                    f"sessao expirada no servidor (HTTP {exc.code})"
                ) from exc
            raise AgentError(
                f"falha ao falar com o servidor em {url} ({exc})"
            ) from exc
        except (OSError, ValueError) as exc:
            raise AgentError(f"falha ao falar com o servidor em {url} ({exc})") from exc

    def _consume_events(self, stream, session_id, on_delta, on_idle, timeout):
        deadline = time.monotonic() + timeout
        parts: dict[str, str] = {}
        roles: dict[str, str] = {}
        done = False
        while not done:
            if time.monotonic() >= deadline:
                raise AgentError("timeout ao aguardar a resposta")
            try:
                raw = stream.readline()
            except (socket.timeout, TimeoutError):
                if on_idle is not None:
                    on_idle()
                continue
            if not raw:
                break
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if not payload:
                continue
            try:
                obj = json.loads(payload)
            except ValueError:
                continue
            etype = obj.get("type")
            props = obj.get("properties") or {}
            if etype == "message.updated":
                info = props.get("info") or {}
                mid = info.get("id")
                role = info.get("role")
                if mid and role:
                    roles[mid] = role
                continue
            if etype == "message.part.updated":
                part = props.get("part") or {}
                if part.get("type") != "text":
                    continue
                if part.get("sessionID") and part["sessionID"] != session_id:
                    continue
                mid = part.get("messageID")
                if mid is not None and roles.get(mid) != "assistant":
                    continue
                pid = part.get("id") or "?"
                new = part.get("text") or ""
                prev = parts.get(pid, "")
                delta = new[len(prev):] if new.startswith(prev) else new
                parts[pid] = new
                if delta:
                    on_delta(delta)
            elif etype in ("session.idle", "session.error"):
                sid = props.get("sessionID")
                if sid and sid != session_id:
                    continue
                done = True
        text = "".join(parts.values()).strip()
        if not text:
            raise AgentError("agente nao retornou resposta")
        return text

    def stream(self, task, on_delta, on_idle=None, timeout_s=None) -> str:
        task = (task or "").strip()
        if not task:
            raise AgentError("tarefa vazia")
        timeout = timeout_s if timeout_s is not None else self._cfg.timeout_s
        session_id = self._ensure_session(timeout)
        url = self._cfg.server_url.rstrip("/") + "/event"
        try:
            events = urllib.request.urlopen(url, timeout=timeout)
        except (OSError, ValueError) as exc:
            raise AgentError(f"falha ao assinar /event ({exc})") from exc
        try:
            payload = {"parts": [{"type": "text", "text": task}]}
            if self._cfg.agent:
                payload["agent"] = self._cfg.agent
            try:
                self._post_no_content(
                    f"/session/{session_id}/prompt_async", payload, timeout
                )
            except _SessionGone:
                self._session_id = None
                session_id = self._ensure_session(timeout)
                self._post_no_content(
                    f"/session/{session_id}/prompt_async", payload, timeout
                )
            return self._consume_events(
                events, session_id, on_delta, on_idle, timeout
            )
        finally:
            try:
                events.close()
            except OSError:
                pass


def make_client(cfg: Config):
    if cfg.agent_backend == "serve":
        return ServeClient(cfg)
    return RunClient(cfg)
