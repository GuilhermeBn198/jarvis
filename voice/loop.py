import sys

from agent_client import AgentError, RunClient
from config import load_config


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
