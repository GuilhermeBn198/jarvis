import sys

from agent_client import AgentError, RunClient
from capture import record
from config import load_config
from stt import transcribe
from tts import VoiceError, speak


def voice_loop(client, iterations: int = 0, record_seconds: float | None = None,
               config=None, err=None) -> None:
    cfg = config or load_config()
    err = err if err is not None else sys.stderr
    secs = record_seconds if record_seconds is not None else cfg.record_seconds
    n = 0
    while iterations == 0 or n < iterations:
        n += 1
        try:
            wav = record(seconds=secs, config=cfg)
            text = transcribe(wav, config=cfg)
        except VoiceError as exc:
            err.write(f"[erro] voz: {exc}\n")
            err.flush()
            continue
        if not text:
            continue
        try:
            answer = client.ask(text)
        except AgentError as exc:
            answer = f"erro: {exc}"
        try:
            speak(answer, config=cfg)
        except VoiceError as exc:
            err.write(f"[erro] voz: {exc}\n")
            err.flush()


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


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if "--voice" in args:
            voice_loop(RunClient(load_config()), iterations=_parse_once(args))
            return 0
        run_stream(sys.stdin, sys.stdout, RunClient(load_config()))
        return 0
    except KeyboardInterrupt:
        sys.stderr.write("\n[voice] encerrado\n")
        sys.stderr.flush()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
