"""Benchmark de latencia da voz: agentes (run/serve) x TTS (sapi/piper).

Rode com: python bench.py
"""
import dataclasses
import time

from agent_client import RunClient, ServeClient
from config import load_config
from tts import speak

TASK = "Responda apenas com a palavra: ok"
TTS_TEXT = "teste de latencia do jarvis"


def _timed(fn):
    start = time.perf_counter()
    result = fn()
    return time.perf_counter() - start, result


def _sibling_wav(path: str, name: str) -> str:
    if "\\" in path:
        return path.rsplit("\\", 1)[0] + "\\" + name
    if "/" in path:
        return path.rsplit("/", 1)[0] + "/" + name
    return name


def _measure(label: str, fn):
    try:
        elapsed, _ = _timed(fn)
        return elapsed
    except Exception as exc:  # noqa: BLE001 - bench nao deve abortar por um backend
        print(f"[bench] {label} falhou: {exc}")
        return None


def _fmt(value) -> str:
    return "n/d" if value is None else f"{value:.2f}"


def _combo(agent, tts):
    if agent is None or tts is None:
        return None
    return agent + tts


def main() -> None:
    cfg = load_config()

    run_client = RunClient(cfg)
    run_cold = _measure("run cold", lambda: run_client.ask(TASK))
    run_warm = _measure("run warm", lambda: run_client.ask(TASK))

    serve_client = ServeClient(cfg)
    serve_cold = _measure("serve cold", lambda: serve_client.ask(TASK))
    serve_warm = _measure("serve warm", lambda: serve_client.ask(TASK))

    sapi_cfg = dataclasses.replace(cfg, tts_backend="sapi")
    piper_cfg = dataclasses.replace(cfg, tts_backend="piper")
    sapi_out = _sibling_wav(cfg.piper_out_wav, "bench_sapi.wav")
    piper_out = _sibling_wav(cfg.piper_out_wav, "bench_piper.wav")
    tts_sapi = _measure(
        "tts sapi", lambda: speak(TTS_TEXT, to_file=sapi_out, config=sapi_cfg)
    )
    tts_piper = _measure(
        "tts piper", lambda: speak(TTS_TEXT, to_file=piper_out, config=piper_cfg)
    )

    print("# Bench de latencia - Jarvis voice")
    print()
    print(f'Tarefa do agente: "{TASK}"')
    print(f'Texto do TTS: "{TTS_TEXT}"')
    print()
    print("| Etapa | Backend | Latencia (s) |")
    print("| --- | --- | --- |")
    print(f"| Agente (frio) | run | {_fmt(run_cold)} |")
    print(f"| Agente (quente) | run | {_fmt(run_warm)} |")
    print(f"| Agente (frio) | serve | {_fmt(serve_cold)} |")
    print(f"| Agente (quente) | serve | {_fmt(serve_warm)} |")
    print(f"| TTS | sapi | {_fmt(tts_sapi)} |")
    print(f"| TTS | piper | {_fmt(tts_piper)} |")
    print()
    print("## Combos (agente quente + TTS)")
    print()
    print("| Agente | TTS | Total (s) |")
    print("| --- | --- | --- |")
    for agent_name, agent_val in (("run", run_warm), ("serve", serve_warm)):
        for tts_name, tts_val in (("sapi", tts_sapi), ("piper", tts_piper)):
            print(f"| {agent_name} | {tts_name} | {_fmt(_combo(agent_val, tts_val))} |")


if __name__ == "__main__":
    main()
