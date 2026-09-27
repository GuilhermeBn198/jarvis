import subprocess

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
