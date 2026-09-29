"""Benchmark de latencia da voz: agentes (run/serve) x TTS (sapi/piper) x visao.

Rode com: python bench.py
"""
import dataclasses
import os
import time

from agent_client import RunClient, ServeClient
from config import load_config
from paths import _windows_to_wsl
from serve import ensure_server
from stream import SentenceChunker
from tts import speak
from vision import _see_via_run, capture

TASK = "Responda apenas com a palavra: ok"
STREAM_TASK = "Explique em 3 frases o que e fuso horario."
TTS_TEXT = "teste de latencia do jarvis"
VISION_TASK = "Descreva em uma frase o que aparece na tela."


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


def _vision_png(cfg) -> str:
    path = _windows_to_wsl(cfg.vision_png)
    if os.path.exists(path):
        return path
    return capture(config=cfg)


def main() -> None:
    cfg = load_config()

    run_client = RunClient(cfg)
    run_cold = _measure("run cold", lambda: run_client.ask(TASK))
    run_second = _measure("run (2ª chamada)", lambda: run_client.ask(TASK))

    serve_client = ServeClient(cfg)
    serve_cold = _measure("serve cold", lambda: serve_client.ask(TASK))
    serve_warm = _measure("serve warm", lambda: serve_client.ask(TASK))

    # Streaming: tempo ate o 1º pedaco (TTS por sentenca) vs resposta completa.
    stream_first = None
    stream_total = None
    try:
        chunker = SentenceChunker(min_chars=cfg.stream_min_chars)
        started = time.perf_counter()
        first = {"t": None}

        def on_delta(d):
            for _ in chunker.feed(d):
                if first["t"] is None:
                    first["t"] = time.perf_counter() - started

        try:
            # Prompt proprio (mais longo que TASK) para garantir um 1º pedaco:
            # a resposta curta de TASK nao atinge min_chars do chunker.
            serve_client.stream(STREAM_TASK, on_delta)
        finally:
            stream_total = time.perf_counter() - started
        stream_first = first["t"]
    except Exception as exc:  # noqa: BLE001 - bench nao deve abortar
        print(f"[bench] streaming falhou: {exc}")

    # Visao: serve (session aquecida) vs run (startup do opencode).
    png = None
    vision_serve = None
    vision_run = None
    try:
        png = _vision_png(cfg)
    except Exception as exc:  # noqa: BLE001
        print(f"[bench] nao consegui obter o PNG de visao: {exc}")
    if png:
        if ensure_server(cfg):
            vision_serve = _measure(
                "visao serve",
                lambda: ServeClient(cfg).see(
                    VISION_TASK, png, model_id=cfg.vision_model
                ),
            )
        else:
            print("[bench] serve indisponivel; pulando visao via serve")
        vision_run = _measure(
            "visao run", lambda: _see_via_run(cfg, VISION_TASK, png)
        )

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
    print(f'Tarefa do streaming: "{STREAM_TASK}"')
    print(f'Tarefa de visao: "{VISION_TASK}"')
    print(f'Texto do TTS: "{TTS_TEXT}"')
    print()
    print("| Etapa | Backend | Latencia (s) |")
    print("| --- | --- | --- |")
    print(f"| Agente (frio) | run | {_fmt(run_cold)} |")
    print(f"| Agente (2ª chamada) | run | {_fmt(run_second)} |")
    print(f"| Agente (frio) | serve | {_fmt(serve_cold)} |")
    print(f"| Agente (quente) | serve | {_fmt(serve_warm)} |")
    print(f"| Streaming: 1º pedaço | serve | {_fmt(stream_first)} |")
    print(f"| Streaming: resposta completa | serve | {_fmt(stream_total)} |")
    print(f"| Visao | serve | {_fmt(vision_serve)} |")
    print(f"| Visao | run | {_fmt(vision_run)} |")
    print(f"| TTS | sapi | {_fmt(tts_sapi)} |")
    print(f"| TTS | piper | {_fmt(tts_piper)} |")
    print()
    print("## Combos (agente + TTS)")
    print()
    print("| Agente | TTS | Total (s) |")
    print("| --- | --- | --- |")
    for agent_name, agent_val in (("run (2ª chamada)", run_second), ("serve (quente)", serve_warm)):
        for tts_name, tts_val in (("sapi", tts_sapi), ("piper", tts_piper)):
            print(f"| {agent_name} | {tts_name} | {_fmt(_combo(agent_val, tts_val))} |")
    print()
    print("## Visao (serve vs run)")
    print()
    print("| Modo | Latencia (s) |")
    print("| --- | --- |")
    print(f"| serve | {_fmt(vision_serve)} |")
    print(f"| run | {_fmt(vision_run)} |")
    if vision_serve is not None and vision_run is not None and vision_run > 0:
        gain = (1.0 - vision_serve / vision_run) * 100.0
        print()
        print(f"Ganho do serve na visao: {gain:.0f}%")


if __name__ == "__main__":
    main()
