import re
import subprocess
import sys
import time
from datetime import datetime, timezone

from agent_client import AgentError, RunClient, make_client, strip_opencode_noise
from capture import record, record_auto, record_ptt
from config import load_config
from convlog import log_turn
from sanitize import speechify
from serve import ensure_server
from stt import transcribe
from tts import VoiceError, speak
from vision import capture, see


def voice_loop(client=None, iterations: int = 0, record_seconds: float | None = None,
               config=None, err=None, max_consecutive_errors: int = 3,
               hub=None, orphan_timeout_s: float = 15.0) -> None:
    cfg = config or load_config()
    err = err if err is not None else sys.stderr
    if client is None:
        client = resolve_client(cfg, err)
    secs = record_seconds if record_seconds is not None else cfg.record_seconds
    n = 0
    consecutive_errors = 0
    if hub is not None:
        hub.set("idle")

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
        t0 = time.monotonic()
        try:
            if hub is not None:
                hub.set("listening")
            if cfg.input_mode == "auto":
                wav = record_auto(config=cfg)
                if not wav:
                    err.write("[voz] nada detectado\n")
                    err.flush()
                    consecutive_errors = 0
                    if hub is not None:
                        hub.set("idle")
                    continue
            elif cfg.input_mode == "ptt":
                wav = record_ptt(config=cfg)
            else:
                wav = record(seconds=secs, config=cfg)
            t_rec = time.monotonic()
            if hub is not None:
                hub.set("transcribing")
            text = transcribe(wav, config=cfg)
        except VoiceError as exc:
            if hub is not None:
                hub.set("error")
            if _voice_error(exc):
                return
            if hub is not None:
                hub.set("idle")
            continue
        t_stt = time.monotonic()
        if not text:
            err.write("[voz] nada transcrito\n")
            err.flush()
            consecutive_errors = 0
            if hub is not None:
                hub.set("idle")
            continue
        if is_vision_request(text, cfg.vision_trigger):
            try:
                see_once(strip_trigger(text, cfg.vision_trigger), err=err, config=cfg, hub=hub)
            except VoiceError as exc:
                if hub is not None:
                    hub.set("error")
                abort = _voice_error(exc)
                if hub is not None:
                    hub.set("idle")
                if abort:
                    return
                continue
            consecutive_errors = 0
            continue
        error = None
        t_agent0 = time.monotonic()
        if hub is not None:
            hub.set("thinking")
        try:
            answer = client.ask(text)
        except AgentError as exc:
            error = str(exc)
            answer = f"erro: {exc}"
            if hub is not None:
                hub.set("error")
        t_agent1 = time.monotonic()
        spoken = speechify(answer)
        aborted = False
        tts_failed = False
        t_tts0 = time.monotonic()
        muted = False
        try:
            if not muted and hub is not None:
                hub.set("speaking")
            if not muted:
                speak(spoken, config=cfg)
        except VoiceError as exc:
            tts_failed = True
            aborted = _voice_error(exc)
            err.write(f"[fallback texto] {answer}\n")
            err.flush()
        t_tts1 = time.monotonic()
        log_turn(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "transcript": text,
                "response": answer,
                "spoken": spoken,
                "agent_backend": cfg.agent_backend,
                "tts_backend": cfg.tts_backend,
                "error": error,
                "record_s": round(t_rec - t0, 3),
                "stt_s": round(t_stt - t_rec, 3),
                "agent_s": round(t_agent1 - t_agent0, 3),
                "tts_s": round(t_tts1 - t_tts0, 3),
            },
            config=cfg,
        )
        if tts_failed:
            if hub is not None:
                hub.set("idle")
            if aborted:
                return
            continue
        consecutive_errors = 0
        if hub is not None:
            hub.set("idle")


def is_vision_request(text: str, trigger: str) -> bool:
    if not trigger:
        return False
    pattern = r"^\s*" + re.escape(trigger) + r"\b"
    return re.match(pattern, text or "", re.IGNORECASE) is not None


def strip_trigger(text: str, trigger: str) -> str:
    t = (text or "").strip()
    if trigger and t.lower().startswith(trigger.lower()):
        return t[len(trigger):].strip()
    return t


def see_once(prompt: str, out=None, err=None, config=None, hub=None) -> None:
    out = out if out is not None else sys.stdout
    err = err if err is not None else sys.stderr
    cfg = config or load_config()
    t0 = time.monotonic()
    png = capture(config=cfg)
    t_cap = time.monotonic()
    if hub is not None:
        hub.set("thinking")
    answer = see(prompt, png, config=cfg)
    t_see = time.monotonic()
    text = answer if isinstance(answer, str) else str(answer)
    spoken = speechify(text)
    out.write(text + "\n")
    out.flush()
    error = None
    try:
        if hub is not None:
            hub.set("speaking")
        speak(spoken, config=cfg)
    except VoiceError as exc:
        error = str(exc)
        err.write(f"[fallback texto] {text}\n")
        err.flush()
    log_turn(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "mode": "vision",
            "prompt": prompt,
            "response": text,
            "spoken": spoken,
            "tts_backend": cfg.tts_backend,
            "error": error,
            "capture_s": round(t_cap - t0, 3),
            "agent_s": round(t_see - t_cap, 3),
        },
        config=cfg,
    )
    if hub is not None:
        hub.set("idle")


def do_once(prompt: str, out=None, err=None, config=None, hub=None) -> None:
    """Executa uma acao no PC pelo agente `act` (modo --do), sem voz.

    Forca `--agent act` independentemente do `agent` configurado; erros viram
    mensagem clara no stderr em vez de crash.
    """
    out = out if out is not None else sys.stdout
    err = err if err is not None else sys.stderr
    cfg = config or load_config()
    prompt = (prompt or "").strip()
    if not prompt:
        err.write("[erro] --do exige um prompt\n")
        err.flush()
        return
    # NAO usar --pure: ele desabilita os plugins do projeto e, com isso, as
    # tools act_* (e o SafetyGate) ficam indisponiveis (verificado via
    # `opencode run --agent act` com/sem --pure).
    if hub is not None:
        hub.set("acting")
    cmd = [cfg.opencode_bin, "run", "--agent", "act", prompt]
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=cfg.timeout_s,
        )
    except FileNotFoundError:
        err.write(
            f"[erro] opencode nao encontrado em {cfg.opencode_bin} "
            f"(defina OPENCODE_BIN)\n"
        )
        err.flush()
        return
    except PermissionError:
        err.write(f"[erro] opencode em {cfg.opencode_bin} nao e executavel\n")
        err.flush()
        return
    except subprocess.TimeoutExpired:
        err.write(f"[erro] timeout ({cfg.timeout_s}s) ao chamar o agente\n")
        err.flush()
        return
    except OSError as exc:
        err.write(f"[erro] falha ao executar opencode ({exc})\n")
        err.flush()
        return
    t_agent = time.monotonic()
    answer = strip_opencode_noise(proc.stdout or "").strip()
    error = None
    if proc.returncode != 0:
        error = (
            f"opencode falhou ({proc.returncode}): "
            f"{(proc.stderr or '').strip()[:200]}"
        )
    if not answer:
        answer = f"erro: {error}" if error else "agente nao retornou resposta"
        error = error or "sem resposta"
    spoken = speechify(answer)
    out.write(answer + "\n")
    out.flush()
    if hub is not None:
        hub.set("idle")
    log_turn(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "mode": "act",
            "prompt": prompt,
            "response": answer,
            "spoken": spoken,
            "error": error,
            "agent_s": round(t_agent - t0, 3),
        },
        config=cfg,
    )


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


def resolve_client(cfg, err=None):
    err = err if err is not None else sys.stderr
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
        if "--see" in args:
            i = args.index("--see")
            question = args[i + 1] if i + 1 < len(args) else ""
            try:
                see_once(question)
            except VoiceError as exc:
                sys.stderr.write(f"[erro] {exc}\n")
                sys.stderr.flush()
                return 1
            return 0
        if "--voice" in args:
            iterations = _parse_once(args)
            if "--once" in args and iterations < 1:
                sys.stderr.write("[erro] --once exige N >= 1\n")
                sys.stderr.flush()
                return 2
            cfg = load_config()
            voice_loop(resolve_client(cfg, sys.stderr), iterations=iterations)
            return 0
        if "--do" in args:
            i = args.index("--do")
            if i + 1 >= len(args):
                sys.stderr.write("[erro] --do exige um prompt\n")
                sys.stderr.flush()
                return 2
            do_once(args[i + 1])
            return 0
        run_stream(sys.stdin, sys.stdout, resolve_client(load_config(), sys.stderr))
        return 0
    except KeyboardInterrupt:
        sys.stderr.write("\n[voice] encerrado\n")
        sys.stderr.flush()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
