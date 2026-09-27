import sys

from agent_client import AgentError, RunClient, make_client
from capture import record
from config import load_config
from serve import ensure_server
from stt import transcribe
from tts import VoiceError, speak


def voice_loop(client=None, iterations: int = 0, record_seconds: float | None = None,
               config=None, err=None, max_consecutive_errors: int = 3) -> None:
    cfg = config or load_config()
    if client is None:
        client = make_client(cfg)
    err = err if err is not None else sys.stderr
    secs = record_seconds if record_seconds is not None else cfg.record_seconds
    n = 0
    consecutive_errors = 0

    def _voice_error(exc: VoiceError) -> bool:
        nonlocal consecutive_errors
        err.write(f"[erro] voz: {exc}\n")
        err.flush()
        consecutive_errors += 1
        if consecutive_errors >= max_consecutive_errors:
            err.write(
                f"[erro] voz: {consecutive_errors} falhas seguidas "
                f"({exc}); abortando\n"
            )
            err.flush()
            return True
        return False

    while iterations == 0 or n < iterations:
        n += 1
        try:
            wav = record(seconds=secs, config=cfg)
            text = transcribe(wav, config=cfg)
        except VoiceError as exc:
            if _voice_error(exc):
                return
            continue
        if not text:
            err.write("[voz] nada transcrito\n")
            err.flush()
            consecutive_errors = 0
            continue
        try:
            answer = client.ask(text)
        except AgentError as exc:
            answer = f"erro: {exc}"
        try:
            speak(answer, config=cfg)
        except VoiceError as exc:
            aborted = _voice_error(exc)
            err.write(f"[fallback texto] {answer}\n")
            err.flush()
            if aborted:
                return
            continue
        consecutive_errors = 0


def run_stream(inp, out, client, err=None) -> None:
    err = err if err is not None else sys.stderr
    for line in inp:
        task = line.strip()
        if not task:
            continue
        try:
            out.write(client.ask(task) + "\n")
            out.flush()
        except AgentError as exc:
            err.write(f"[erro] {exc}\n")
            err.flush()


def _parse_once(args) -> int:
    if "--once" not in args:
        return 0
    i = args.index("--once")
    if i + 1 >= len(args):
        return 1
    try:
        return int(args[i + 1])
    except ValueError:
        return 1


def _resolve_client(cfg, err):
    if cfg.agent_backend == "serve":
        if ensure_server(cfg):
            return make_client(cfg)
        err.write(
            "[aviso] serve indisponivel; usando backend 'run' (mais lento)\n"
        )
        err.flush()
        return RunClient(cfg)
    return make_client(cfg)


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if "--voice" in args:
            iterations = _parse_once(args)
            if "--once" in args and iterations < 1:
                sys.stderr.write("[erro] --once exige N >= 1\n")
                sys.stderr.flush()
                return 2
            cfg = load_config()
            voice_loop(_resolve_client(cfg, sys.stderr), iterations=iterations)
            return 0
        run_stream(sys.stdin, sys.stdout, make_client(load_config()))
        return 0
    except KeyboardInterrupt:
        sys.stderr.write("\n[voice] encerrado\n")
        sys.stderr.flush()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
