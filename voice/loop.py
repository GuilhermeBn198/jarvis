import fcntl
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from agent_client import AgentError, RunClient, make_client, strip_opencode_noise
from capture import QuitRequested, measure_level, record, record_auto, record_ptt
from config import load_config
from convlog import log_turn
from sanitize import speechify
from serve import ensure_server
from state import StateHub
from stt import transcribe
from stream import SentenceChunker, Speaker
from tts import VoiceError, speak
from vision import capture, see


def gui_lost(require_gui: bool, subscribers: int, last_gui_ts: float,
             now: float, timeout: float) -> bool:
    if not require_gui:
        return False
    if subscribers > 0:
        return False
    return (now - last_gui_ts) > timeout


def _emit(hub, state, detail=None) -> None:
    """Publica um estado no hub, se houver, sem nunca derrubar a voz.

    Qualquer falha do hub (ausente, desconectado, com `set` quebrado) e
    engolida: o indicador nunca pode interromper o loop de voz.
    """
    if hub is None:
        return
    try:
        if detail is None:
            hub.set(state)
        else:
            hub.set(state, detail)
    except Exception:
        pass


@dataclass
class StreamResult:
    answer: str | None
    spoken: list[str]
    first_audio_s: float | None
    streamed: bool
    failed: str | None
    gen_done_s: float | None = None
    voice_error: Exception | None = None


def _first_audio(speaker, t0):
    if speaker is None or speaker.first_speak_ts is None:
        return None
    return round(speaker.first_speak_ts - t0, 3)


def _stream_turn(client, text, cfg, hub, muted, t0, err) -> StreamResult:
    """Tenta falar por streaming. NAO chama ask() — o fallback e do voice_loop."""
    chunker = SentenceChunker(min_chars=cfg.stream_min_chars)
    speaker = Speaker(cfg) if not muted else None
    spoken: list[str] = []
    raw_parts: list[str] = []
    failed: str | None = None
    answer: str | None = None
    voice_error: Exception | None = None
    gen_done_s: float | None = None
    spoke_started = False

    def emit(chunks):
        nonlocal spoke_started
        for chunk in chunks:
            spoken_text = speechify(chunk)
            if spoken_text:
                spoken.append(spoken_text)
                if speaker is not None:
                    if not spoke_started:
                        spoke_started = True
                        _emit(hub, "speaking")
                    speaker.say(spoken_text)

    def on_delta(delta):
        raw_parts.append(delta)
        emit(chunker.feed(delta))

    try:
        answer = client.stream(
            text,
            on_delta,
            lambda: emit(chunker.flush()),
            timeout_s=cfg.timeout_s,
        )
        emit(chunker.flush())
        # Geracao terminou: medido ANTES de speaker.close()/join(), para que
        # agent_s nao inclua o playback do TTS.
        gen_done_s = round(time.monotonic() - t0, 3)
    except Exception as exc:  # fronteira: streaming NUNCA pode derrubar a voz
        failed = str(exc)
    finally:
        if speaker is not None:
            speaker.close()
            speaker.join()
            if speaker.error is not None:
                voice_error = speaker.error
                if failed is None:
                    failed = str(speaker.error)
    if failed is not None:
        err.write(f"[voz] streaming falhou ({failed})\n")
        err.flush()
    raw_text = "".join(raw_parts)
    # Em falha no meio do stream, `answer` e None: preserva a resposta crua
    # parcial para o log. Se nada foi gerado, permanece None e o voice_loop
    # cai no ask() bloqueante (nao ha re-pergunta indevida).
    answer = answer or raw_text or None
    streamed = failed is None and answer is not None
    return StreamResult(answer, spoken, _first_audio(speaker, t0), streamed, failed,
                        gen_done_s, voice_error)


def _measure_mic(cfg, hub, err) -> None:
    """Mede o microfone (para calibrar VOICE_NOISE_DB) e publica o resultado."""
    _emit(hub, "idle", "medindo microfone")
    try:
        lvl = measure_level(config=cfg)
        result = dict(lvl)
        mean = lvl.get("mean_db")
        if mean is not None:
            result["suggested_noise_db"] = int(round(mean + 8))
        result["ok"] = True
    except VoiceError as exc:
        result = {"ok": False, "error": str(exc)}
    if hub is not None:
        try:
            hub.set_measure_result(result)
        except Exception:
            pass
    _emit(hub, "idle")


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
    if cfg.state_require_gui and hub is None:
        # Sem indicador nao ha como o anti-orfao funcionar; rodar assim seria
        # um loop headless segurando o microfone (issue #4). Nao roda.
        err.write(
            "[erro] overlay exigido (JARVIS_REQUIRE_GUI) mas o indicador nao "
            "subiu; encerrando para nao rodar headless\n"
        )
        err.flush()
        return
    _emit(hub, "idle")
    last_gui_ts = time.monotonic()
    muted = False
    paused = False
    was_paused = False
    measure_requested = False

    def _should_stop() -> bool:
        """Checa comandos DURANTE a gravacao; True se pediram `quit`.

        Drena a fila (tratando mute/pause/measure) para que o botao Sair tenha
        efeito em ~0.2s, em vez de esperar o fim do `record_auto`.
        """
        nonlocal muted, paused, measure_requested
        if hub is None:
            return False
        try:
            cmd = hub.take_command()
        except Exception:
            return False
        stop = False
        while cmd is not None:
            if cmd == "quit":
                stop = True
            elif cmd == "mute":
                muted = not muted
            elif cmd == "pause":
                paused = not paused
            elif cmd == "measure":
                measure_requested = True
            try:
                cmd = hub.take_command()
            except Exception:
                cmd = None
        return stop

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
        if hub is not None:
            try:
                cmd = hub.take_command()
            except Exception:
                cmd = None
            while cmd is not None:
                if cmd == "quit":
                    return
                if cmd == "mute":
                    muted = not muted
                elif cmd == "pause":
                    paused = not paused
                elif cmd == "measure":
                    measure_requested = True
                try:
                    cmd = hub.take_command()
                except Exception:
                    cmd = None
            try:
                subs = hub.subscribers()
            except Exception:
                subs = 0
            now = time.monotonic()
            if subs > 0:
                last_gui_ts = now
            elif gui_lost(cfg.state_require_gui, subs, last_gui_ts, now, orphan_timeout_s):
                err.write("[voz] overlay ausente; encerrando\n")
                err.flush()
                return
            if paused:
                if not was_paused:
                    _emit(hub, "idle")
                    was_paused = True
                time.sleep(0.25)
                continue
            was_paused = False
            if measure_requested:
                measure_requested = False
                _measure_mic(cfg, hub, err)
                continue
        t0 = time.monotonic()
        try:
            _emit(hub, "listening")
            if cfg.input_mode == "auto":
                wav = record_auto(config=cfg, should_stop=_should_stop)
                if not wav:
                    err.write("[voz] nada detectado\n")
                    err.flush()
                    consecutive_errors = 0
                    _emit(hub, "idle")
                    continue
            elif cfg.input_mode == "ptt":
                wav = record_ptt(config=cfg)
            else:
                wav = record(seconds=secs, config=cfg)
            t_rec = time.monotonic()
            _emit(hub, "transcribing")
            text = transcribe(wav, config=cfg)
        except QuitRequested:
            return
        except VoiceError as exc:
            _emit(hub, "error")
            if _voice_error(exc):
                return
            _emit(hub, "idle")
            continue
        t_stt = time.monotonic()
        if not text:
            err.write("[voz] nada transcrito\n")
            err.flush()
            consecutive_errors = 0
            _emit(hub, "idle")
            continue
        if is_vision_request(text, cfg.vision_trigger):
            try:
                see_once(strip_trigger(text, cfg.vision_trigger), err=err, config=cfg, hub=hub)
            except VoiceError as exc:
                _emit(hub, "error")
                abort = _voice_error(exc)
                if abort:
                    return
                _emit(hub, "idle")
                continue
            consecutive_errors = 0
            continue
        error = None
        t_agent0 = time.monotonic()
        _emit(hub, "thinking")
        first_audio = None
        streamed = False
        tts_failed = False
        aborted = False
        answer = None
        t_agent1 = None
        t_tts0 = t_agent0
        if cfg.stream_tts and hasattr(client, "stream"):
            res = _stream_turn(client, text, cfg, hub, muted, t_agent0, err)
            if res.gen_done_s is not None:
                t_agent1 = t_agent0 + res.gen_done_s
                # O TTS do streaming toca em paralelo a geracao; tts_s mede o
                # playback residual a partir do fim da geracao (pode sobrepor
                # ao agent_s, que agora conta so a geracao).
                t_tts0 = t_agent1
            else:
                t_agent1 = time.monotonic()
            first_audio = res.first_audio_s
            if res.voice_error is not None:
                tts_failed = True
                aborted = _voice_error(res.voice_error)
            if res.streamed or res.spoken:
                answer = res.answer or " ".join(res.spoken)
                spoken = " ".join(res.spoken)
                streamed = res.streamed
                error = res.failed
        if answer is None:
            try:
                answer = client.ask(text)
            except AgentError as exc:
                error = str(exc)
                answer = f"erro: {exc}"
                _emit(hub, "error")
            t_agent1 = time.monotonic()
            spoken = speechify(answer)
            t_tts0 = time.monotonic()
            try:
                if not muted:
                    _emit(hub, "speaking")
                if not muted:
                    speak(spoken, config=cfg)
            except VoiceError as exc:
                tts_failed = True
                aborted = _voice_error(exc)
                err.write(f"[fallback texto] {answer}\n")
                err.flush()
        if t_agent1 is None:
            t_agent1 = time.monotonic()
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
                "stream": streamed,
                "first_audio_s": first_audio,
            },
            config=cfg,
        )
        if tts_failed:
            if aborted:
                _emit(hub, "error")
                return
            _emit(hub, "idle")
            continue
        consecutive_errors = 0
        _emit(hub, "idle")


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
    _emit(hub, "thinking")
    answer = see(prompt, png, config=cfg)
    t_see = time.monotonic()
    text = answer if isinstance(answer, str) else str(answer)
    spoken = speechify(text)
    out.write(text + "\n")
    out.flush()
    error = None
    try:
        _emit(hub, "speaking")
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
    _emit(hub, "idle")


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
    _emit(hub, "acting")
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
        _emit(hub, "idle")
        return
    except PermissionError:
        err.write(f"[erro] opencode em {cfg.opencode_bin} nao e executavel\n")
        err.flush()
        _emit(hub, "idle")
        return
    except subprocess.TimeoutExpired:
        err.write(f"[erro] timeout ({cfg.timeout_s}s) ao chamar o agente\n")
        err.flush()
        _emit(hub, "idle")
        return
    except OSError as exc:
        err.write(f"[erro] falha ao executar opencode ({exc})\n")
        err.flush()
        _emit(hub, "idle")
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
    _emit(hub, "idle")
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


def _start_hub(cfg, err):
    try:
        hub = StateHub(cfg.state_port)
        hub.start()
        return hub
    except Exception as exc:
        err.write(f"[aviso] indicador indisponivel ({exc}); seguindo sem ele\n")
        err.flush()
        return None


DEFAULT_VOICE_LOCK = "/tmp/jarvis-voice.lock"


def acquire_singleton(path: str):
    """Trava exclusiva (flock) contra dois loops de voz simultaneos.

    Retorna `(fd, ok)`: `ok=False` se outro loop ja tem a trava. Se nao for
    possivel abrir o arquivo, degrada para `(None, True)` (nao bloqueia).
    """
    try:
        fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    except OSError:
        return None, True
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return None, False
    return fd, True


def release_singleton(fd) -> None:
    if fd is None:
        return
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        os.close(fd)
    except OSError:
        pass


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if "--mic-level" in args:
            cfg = load_config()
            try:
                lvl = measure_level(config=cfg)
            except VoiceError as exc:
                sys.stderr.write(f"[erro] {exc}\n")
                sys.stderr.flush()
                return 1
            mean = lvl.get("mean_db")
            mx = lvl.get("max_db")
            sys.stdout.write(
                f"nivel do microfone: media={mean} dB, pico={mx} dB\n"
            )
            if mean is not None:
                sug = int(round(mean + 8))
                sys.stdout.write(
                    f"VOICE_NOISE_DB sugerido: {sug} "
                    f"(ruido de fundo ~{mean} dB + 8)\n"
                )
            sys.stdout.flush()
            return 0
        if "--see" in args:
            i = args.index("--see")
            question = args[i + 1] if i + 1 < len(args) else ""
            cfg = load_config()
            hub = _start_hub(cfg, sys.stderr)
            try:
                see_once(question, config=cfg, hub=hub)
            except VoiceError as exc:
                sys.stderr.write(f"[erro] {exc}\n")
                sys.stderr.flush()
                return 1
            finally:
                if hub is not None:
                    hub.stop()
            return 0
        if "--voice" in args:
            iterations = _parse_once(args)
            if "--once" in args and iterations < 1:
                sys.stderr.write("[erro] --once exige N >= 1\n")
                sys.stderr.flush()
                return 2
            cfg = load_config()
            lock_fd, ok = acquire_singleton(
                os.environ.get("JARVIS_VOICE_LOCK", DEFAULT_VOICE_LOCK)
            )
            if not ok:
                sys.stderr.write(
                    "[erro] ja existe um loop de voz rodando (lock); saindo\n"
                )
                sys.stderr.flush()
                return 3
            hub = _start_hub(cfg, sys.stderr)
            try:
                voice_loop(resolve_client(cfg, sys.stderr), iterations=iterations,
                           config=cfg, hub=hub)
            finally:
                if hub is not None:
                    hub.stop()
                release_singleton(lock_fd)
            return 0
        if "--do" in args:
            i = args.index("--do")
            if i + 1 >= len(args):
                sys.stderr.write("[erro] --do exige um prompt\n")
                sys.stderr.flush()
                return 2
            cfg = load_config()
            hub = _start_hub(cfg, sys.stderr)
            try:
                do_once(args[i + 1], config=cfg, hub=hub)
            finally:
                if hub is not None:
                    hub.stop()
            return 0
        run_stream(sys.stdin, sys.stdout, resolve_client(load_config(), sys.stderr))
        return 0
    except KeyboardInterrupt:
        sys.stderr.write("\n[voice] encerrado\n")
        sys.stderr.flush()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
