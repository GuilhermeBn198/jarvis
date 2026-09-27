import sys

from agent_client import AgentError, RunClient
from capture import record
from config import load_config
from stt import transcribe
from tts import speak


def voice_loop(client, iterations: int = 0, record_seconds: float | None = None,
               config=None) -> None:
    cfg = config or load_config()
    secs = record_seconds if record_seconds is not None else cfg.record_seconds
    n = 0
    while iterations == 0 or n < iterations:
        n += 1
        wav = record(seconds=secs)
        text = transcribe(wav)
        if not text:
            continue
        try:
            answer = client.ask(text)
        except AgentError as exc:
            answer = f"erro: {exc}"
        speak(answer)


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


def main() -> int:
    run_stream(sys.stdin, sys.stdout, RunClient(load_config()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
