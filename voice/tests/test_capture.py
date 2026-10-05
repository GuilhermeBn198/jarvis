import io, subprocess, threading, pytest
from config import Config
from capture import record, record_auto, record_ptt, VoiceError

CFG = Config(opencode_bin="/x/o", timeout_s=10, ffmpeg_exe="/ff/ffmpeg.exe", mic_device="Mic X", record_seconds=5)


class FakeStdin:
    def __init__(self):
        self.data = b""
    def write(self, b):
        self.data += b
    def flush(self):
        pass


class FakeProc:
    def __init__(self, cmd):
        self.cmd = cmd
        self.stdin = FakeStdin()
        self.returncode = 0
        self.waited = None
        self.killed = False
    def wait(self, timeout=None):
        self.waited = timeout
        return self.returncode
    def poll(self):
        return None if self.waited is None else self.returncode
    def kill(self):
        self.killed = True


class HangingProc(FakeProc):
    def __init__(self, cmd):
        super().__init__(cmd)
        self.alive = True
    def wait(self, timeout=None):
        if self.alive:
            raise subprocess.TimeoutExpired(self.cmd, timeout)
        self.waited = timeout
        return self.returncode
    def poll(self):
        return None if self.alive else self.returncode
    def kill(self):
        self.killed = True
        self.alive = False

def test_record_builds_dshow_command(monkeypatch, tmp_path):
    seen = {}
    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(subprocess, "run", fake_run)
    out = str(tmp_path / "a.wav")
    record(3, out_path=out, config=CFG)
    joined = " ".join(seen["cmd"])
    assert "/ff/ffmpeg.exe" in joined
    assert "-f dshow" in joined
    assert 'audio=Mic X' in joined
    assert "-t 3" in joined
    assert out in seen["cmd"]

def test_missing_ffmpeg_raises(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError()))
    with pytest.raises(VoiceError, match="FFMPEG_EXE=/ff/ffmpeg.exe"):
        record(1, out_path="/tmp/x.wav", config=CFG)


def test_record_ptt_starts_ffmpeg_and_stops_with_q(monkeypatch, tmp_path):
    seen = {}
    def fake_popen(cmd, **kw):
        proc = FakeProc(cmd)
        seen["cmd"] = cmd
        seen["kw"] = kw
        seen["proc"] = proc
        return proc
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    out = str(tmp_path / "a.wav")
    prompts = []
    result = record_ptt(out_path=out, config=CFG, prompt_fn=prompts.append)
    joined = " ".join(seen["cmd"])
    assert "/ff/ffmpeg.exe" in joined
    assert "-f dshow" in joined
    assert "audio=Mic X" in joined
    assert out in seen["cmd"]
    assert "comecar" in prompts[0]
    assert "parar" in prompts[1]
    assert seen["proc"].stdin.data == b"q"
    assert seen["proc"].waited == 20
    assert seen["proc"].killed is False
    assert seen["kw"]["stderr"] is subprocess.DEVNULL
    assert result == out


def test_record_ptt_missing_ffmpeg_raises(monkeypatch):
    monkeypatch.setattr(
        subprocess, "Popen",
        lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError()),
    )
    with pytest.raises(VoiceError, match="FFMPEG_EXE=/ff/ffmpeg.exe"):
        record_ptt(out_path="/tmp/x.wav", config=CFG, prompt_fn=lambda *a: None)


def test_record_ptt_nonzero_raises(monkeypatch):
    class BadProc(FakeProc):
        def __init__(self, cmd):
            super().__init__(cmd)
            self.returncode = 1
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: BadProc(cmd))
    with pytest.raises(VoiceError, match="ffmpeg falhou"):
        record_ptt(out_path="/tmp/x.wav", config=CFG, prompt_fn=lambda *a: None)


def test_record_ptt_kills_and_reaps_on_timeout(monkeypatch):
    seen = {}
    def fake_popen(cmd, **kw):
        proc = HangingProc(cmd)
        seen["proc"] = proc
        return proc
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    with pytest.raises(VoiceError, match="falha ao gravar audio"):
        record_ptt(out_path="/tmp/x.wav", config=CFG, prompt_fn=lambda *a: None)
    assert seen["proc"].killed is True
    assert seen["proc"].waited == 5


def test_record_ptt_kills_and_reaps_on_broken_pipe(monkeypatch):
    seen = {}
    def fake_popen(cmd, **kw):
        proc = FakeProc(cmd)
        def boom(_):
            raise BrokenPipeError("pipe fechado")
        proc.stdin.write = boom
        seen["proc"] = proc
        return proc
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    with pytest.raises(VoiceError, match="falha ao gravar audio"):
        record_ptt(out_path="/tmp/x.wav", config=CFG, prompt_fn=lambda *a: None)
    assert seen["proc"].killed is True
    assert seen["proc"].waited == 5


class FakeAutoStdin:
    def __init__(self):
        self.data = ""
    def write(self, s):
        self.data += s
    def flush(self):
        pass


class BlockingStderr:
    def __init__(self, lines):
        self._lines = list(lines)
        self.release = threading.Event()
    def __iter__(self):
        for line in self._lines:
            yield line
        self.release.wait(timeout=5)


class FakeAutoProc:
    def __init__(self, cmd, lines, block=False):
        self.cmd = cmd
        self.stdin = FakeAutoStdin()
        self.stderr = BlockingStderr(lines) if block else iter(list(lines))
        self.returncode = 0
        self.waited = None
        self.killed = False
    def wait(self, timeout=None):
        self.waited = timeout
        return self.returncode
    def poll(self):
        return None if self.waited is None else self.returncode
    def kill(self):
        self.killed = True


def test_record_auto_stops_on_silence_after_speech(monkeypatch):
    seen = {}
    lines = [
        "[silencedetect @ 0x1] silence_end: 1.00 | silence_duration: 2.0\n",
        "[silencedetect @ 0x1] silence_start: 3.00\n",
    ]
    def fake_popen(cmd, **kw):
        proc = FakeAutoProc(cmd, lines)
        seen["cmd"] = cmd
        seen["kw"] = kw
        seen["proc"] = proc
        return proc
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    out = r"C:\Users\user\tools\x.wav"
    result = record_auto(out_path=out, config=CFG)
    joined = " ".join(seen["cmd"])
    assert "/ff/ffmpeg.exe" in joined
    assert "-f dshow" in joined
    assert "audio=Mic X" in joined
    assert "silencedetect=noise=-35dB:d=1.0" in joined
    assert "-t 15" in joined
    assert "C:\\Users\\user\\tools\\x.wav" in seen["cmd"]
    assert seen["kw"]["stderr"] is subprocess.PIPE
    assert seen["kw"]["text"] is True
    assert seen["proc"].stdin.data == "q"
    assert seen["proc"].waited == 20
    assert seen["proc"].killed is False
    assert result == "/mnt/c/Users/user/tools/x.wav"


def test_record_auto_emite_on_level_fala_e_silencio(monkeypatch):
    levels = []
    lines = [
        "[silencedetect @ 0x1] silence_end: 1.00 | silence_duration: 2.0\n",
        "[silencedetect @ 0x1] silence_start: 3.00\n",
    ]
    def fake_popen(cmd, **kw):
        return FakeAutoProc(cmd, lines)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    record_auto(config=CFG, on_level=levels.append)
    # Fala detectada (silence_end) -> 1.0; fim de fala (silence_start) -> 0.0.
    assert 1.0 in levels
    assert 0.0 in levels
    assert levels[0] == 1.0


def test_record_auto_leading_silence_then_speech_stops(monkeypatch):
    seen = {}
    lines = [
        "[silencedetect @ 0x1] silence_start: 0\n",
        "[silencedetect @ 0x1] silence_end: 1.19 | silence_duration: 1.19\n",
        "[silencedetect @ 0x1] silence_start: 3.80\n",
    ]
    def fake_popen(cmd, **kw):
        proc = FakeAutoProc(cmd, lines)
        seen["proc"] = proc
        return proc
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    out = r"C:\Users\user\tools\x.wav"
    result = record_auto(out_path=out, config=CFG)
    assert seen["proc"].stdin.data == "q"
    assert seen["proc"].waited == 20
    assert result == "/mnt/c/Users/user/tools/x.wav"


def test_record_auto_immediate_speech_without_silence_end(monkeypatch):
    seen = {}
    lines = ["[silencedetect @ 0x1] silence_start: 2.80\n"]
    def fake_popen(cmd, **kw):
        proc = FakeAutoProc(cmd, lines)
        seen["proc"] = proc
        return proc
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    out = r"C:\Users\user\tools\x.wav"
    result = record_auto(out_path=out, config=CFG)
    assert seen["proc"].stdin.data == "q"
    assert seen["proc"].waited == 20
    assert result == "/mnt/c/Users/user/tools/x.wav"


def test_record_auto_leading_silence_only_returns_empty(monkeypatch):
    seen = {}
    lines = ["[silencedetect @ 0x1] silence_start: 0\n"]
    def fake_popen(cmd, **kw):
        proc = FakeAutoProc(cmd, lines, block=True)
        seen["proc"] = proc
        return proc
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    try:
        result = record_auto(out_path="/tmp/x.wav", config=CFG, wait_s=0.3)
    finally:
        seen["proc"].stderr.release.set()
    assert result == ""
    assert seen["proc"].stdin.data == ""
    assert seen["proc"].killed is True


def test_record_auto_returns_empty_when_no_speech(monkeypatch):
    seen = {}
    lines = ["[silencedetect @ 0x1] silence_start: 0\n"]
    def fake_popen(cmd, **kw):
        proc = FakeAutoProc(cmd, lines, block=True)
        seen["proc"] = proc
        return proc
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    try:
        result = record_auto(out_path="/tmp/x.wav", config=CFG, wait_s=0.3)
    finally:
        seen["proc"].stderr.release.set()
    assert result == ""
    assert seen["proc"].stdin.data == ""
    assert seen["proc"].killed is True
    assert seen["proc"].waited == 5


def test_record_auto_honors_max_s_cap(monkeypatch):
    seen = {}
    lines = ["[silencedetect @ 0x1] silence_end: 0.5\n"]
    def fake_popen(cmd, **kw):
        proc = FakeAutoProc(cmd, lines, block=True)
        seen["proc"] = proc
        seen["cmd"] = cmd
        return proc
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    try:
        result = record_auto(out_path="/tmp/x.wav", config=CFG, max_s=0.3, wait_s=8)
    finally:
        seen["proc"].stderr.release.set()
    assert result == "/tmp/x.wav"
    assert seen["proc"].stdin.data == "q"
    assert seen["proc"].waited == 20
    assert seen["proc"].killed is False
    assert "-t 0.3" in " ".join(seen["cmd"])


def test_record_auto_missing_ffmpeg_raises(monkeypatch):
    monkeypatch.setattr(
        subprocess, "Popen",
        lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError()),
    )
    with pytest.raises(VoiceError, match="FFMPEG_EXE=/ff/ffmpeg.exe"):
        record_auto(out_path="/tmp/x.wav", config=CFG)


def test_parse_volume_extracts_mean_and_max():
    from capture import parse_volume
    stderr = (
        "[Parsed_volumedetect_0 @ 0x1] mean_volume: -42.3 dB\n"
        "[Parsed_volumedetect_0 @ 0x1] max_volume: -18.7 dB\n"
    )
    assert parse_volume(stderr) == {"mean_db": -42.3, "max_db": -18.7}
    assert parse_volume("nada aqui") == {"mean_db": None, "max_db": None}


def test_measure_level_parses_ffmpeg_output(monkeypatch):
    from capture import measure_level

    class Proc:
        returncode = 0
        stderr = "mean_volume: -50.0 dB\nmax_volume: -20.0 dB\n"

    monkeypatch.setattr("capture.subprocess.run", lambda *a, **k: Proc())
    assert measure_level(seconds=1, config=CFG) == {"mean_db": -50.0, "max_db": -20.0}


def test_measure_level_error_raises(monkeypatch):
    from capture import measure_level

    class Proc:
        returncode = 1
        stderr = "boom"

    monkeypatch.setattr("capture.subprocess.run", lambda *a, **k: Proc())
    try:
        measure_level(seconds=1, config=CFG)
        assert False, "deveria levantar"
    except VoiceError:
        pass


def test_record_auto_rejects_short_noise_then_accepts_speech(monkeypatch):
    seen = {}
    lines = [
        "[silencedetect @ 0x1] silence_end: 0.10\n",
        "[silencedetect @ 0x1] silence_start: 0.30\n",   # ruido de 0.20s: ignora
        "[silencedetect @ 0x1] silence_end: 1.00\n",
        "[silencedetect @ 0x1] silence_start: 3.00\n",   # fala de 2.0s: aceita
    ]
    def fake_popen(cmd, **kw):
        proc = FakeAutoProc(cmd, lines, block=True)
        seen["proc"] = proc
        return proc
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    try:
        result = record_auto(out_path="/tmp/x.wav", config=CFG)
    finally:
        seen["proc"].stderr.release.set()
    assert result == "/tmp/x.wav"
    assert seen["proc"].stdin.data == "q"


def test_record_auto_short_noise_only_returns_empty(monkeypatch):
    seen = {}
    lines = [
        "[silencedetect @ 0x1] silence_end: 0.10\n",
        "[silencedetect @ 0x1] silence_start: 0.30\n",
    ]
    def fake_popen(cmd, **kw):
        proc = FakeAutoProc(cmd, lines, block=True)
        seen["proc"] = proc
        return proc
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    try:
        result = record_auto(out_path="/tmp/x.wav", config=CFG, wait_s=0.3)
    finally:
        seen["proc"].stderr.release.set()
    assert result == ""


def test_record_auto_should_stop_raises_quitrequested(monkeypatch):
    from capture import QuitRequested
    seen = {}
    def fake_popen(cmd, **kw):
        proc = FakeAutoProc(cmd, [], block=True)
        seen["proc"] = proc
        return proc
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    with pytest.raises(QuitRequested):
        record_auto(out_path="/tmp/x.wav", config=CFG, should_stop=lambda: True)
    assert seen["proc"].killed is True


def test_parse_audio_devices_filters_audio_and_dedups():
    from capture import parse_audio_devices
    stderr = (
        '[dshow @ 0x1] "Microphone (FIFINE Microphone)" (audio)\n'
        '[dshow @ 0x1]   Alternative name "@device_cm_{X}\\wave_{Y}"\n'
        '[dshow @ 0x1] "Microphone (Realtek(R) Audio)" (audio)\n'
        '[dshow @ 0x1] "Webcam C920" (video, audio)\n'
        '[dshow @ 0x1] "Microphone (FIFINE Microphone)" (audio)\n'
        '[dshow @ 0x1] "Integrated Camera" (video)\n'
    )
    assert parse_audio_devices(stderr) == [
        "Microphone (FIFINE Microphone)",
        "Microphone (Realtek(R) Audio)",
        "Webcam C920",
    ]
    assert parse_audio_devices("") == []


def test_list_audio_devices_runs_ffmpeg_and_parses(monkeypatch):
    from capture import list_audio_devices
    seen = {}

    class Proc:
        returncode = 1
        stderr = '[dshow @ 0x1] "Mic A" (audio)\n[dshow @ 0x1] "Cam" (video)\n'

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return Proc()

    monkeypatch.setattr("capture.subprocess.run", fake_run)
    assert list_audio_devices(config=CFG) == ["Mic A"]
    joined = " ".join(seen["cmd"])
    assert "-list_devices true" in joined
    assert "-f dshow" in joined


def test_list_audio_devices_missing_ffmpeg_raises(monkeypatch):
    from capture import list_audio_devices
    monkeypatch.setattr(
        "capture.subprocess.run",
        lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError()),
    )
    with pytest.raises(VoiceError, match="FFMPEG_EXE=/ff/ffmpeg.exe"):
        list_audio_devices(config=CFG)
