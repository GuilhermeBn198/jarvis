import json

import serve
from config import Config

CFG = Config(
    opencode_bin="/x/opencode",
    timeout_s=10,
    server_url="http://127.0.0.1:4096",
)


class _Resp:
    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


def test_is_healthy_true(monkeypatch):
    monkeypatch.setattr(
        serve.urllib.request, "urlopen", lambda url, timeout=None: _Resp(b'{"healthy": true}')
    )
    assert serve.is_healthy("http://127.0.0.1:4096") is True


def test_is_healthy_false_on_error(monkeypatch):
    def boom(url, timeout=None):
        raise OSError("recusado")
    monkeypatch.setattr(serve.urllib.request, "urlopen", boom)
    assert serve.is_healthy("http://127.0.0.1:4096") is False


def test_is_healthy_false_on_bad_json(monkeypatch):
    monkeypatch.setattr(
        serve.urllib.request, "urlopen", lambda url, timeout=None: _Resp(b"nope")
    )
    assert serve.is_healthy("http://127.0.0.1:4096") is False


def test_ensure_server_already_healthy(monkeypatch):
    monkeypatch.setattr(serve, "is_healthy", lambda url, timeout=2: True)

    def boom(*a, **k):
        raise AssertionError("nao deve subir o servidor")
    monkeypatch.setattr(serve.subprocess, "Popen", boom)
    assert serve.ensure_server(CFG) is True


def test_ensure_server_spawns_and_waits(monkeypatch, tmp_path):
    monkeypatch.setenv("SERVE_LOG", str(tmp_path / "serve.log"))
    calls = {"n": 0}

    def health(url, timeout=2):
        calls["n"] += 1
        return calls["n"] >= 2
    monkeypatch.setattr(serve, "is_healthy", health)
    spawned = {}

    def popen(cmd, **kw):
        spawned["cmd"] = cmd
        spawned["kw"] = kw
        return object()
    monkeypatch.setattr(serve.subprocess, "Popen", popen)
    assert serve.ensure_server(CFG, wait_s=5) is True
    assert spawned["cmd"] == ["/x/opencode", "serve", "--port", "4096"]
    assert spawned["kw"]["start_new_session"] is True
    assert spawned["kw"]["stdin"] == serve.subprocess.DEVNULL


def test_ensure_server_spawn_failure_returns_false(monkeypatch, tmp_path):
    monkeypatch.setenv("SERVE_LOG", str(tmp_path / "serve.log"))
    monkeypatch.setattr(serve, "is_healthy", lambda url, timeout=2: False)

    def popen(*a, **k):
        raise OSError("binario ausente")
    monkeypatch.setattr(serve.subprocess, "Popen", popen)
    assert serve.ensure_server(CFG, wait_s=1) is False


def test_ensure_server_never_healthy_returns_false(monkeypatch, tmp_path):
    monkeypatch.setenv("SERVE_LOG", str(tmp_path / "serve.log"))
    monkeypatch.setattr(serve, "is_healthy", lambda url, timeout=2: False)
    monkeypatch.setattr(serve.subprocess, "Popen", lambda *a, **k: object())
    monkeypatch.setattr(serve.time, "sleep", lambda s: None)
    ticks = iter([0.0, 0.0, 10.0])
    monkeypatch.setattr(serve.time, "monotonic", lambda: next(ticks))
    assert serve.ensure_server(CFG, wait_s=5) is False


def test_spawn_handles_log_without_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SERVE_LOG", "serve.log")
    monkeypatch.setattr(serve, "is_healthy", lambda url, timeout=2: False)
    spawned = {}
    monkeypatch.setattr(
        serve.subprocess, "Popen",
        lambda cmd, **kw: spawned.update(kw) or object(),
    )
    monkeypatch.setattr(serve.time, "sleep", lambda s: None)
    ticks = iter([0.0, 10.0])
    monkeypatch.setattr(serve.time, "monotonic", lambda: next(ticks))
    assert serve.ensure_server(CFG, wait_s=1) is False
    assert spawned["stdout"] != serve.subprocess.DEVNULL


def test_ensure_server_never_raises(monkeypatch):
    def boom(url, timeout=2):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(serve, "is_healthy", boom)
    assert serve.ensure_server(CFG) is False


def test_spawn_sets_project_root_cwd(monkeypatch):
    import serve as s
    seen = {}
    monkeypatch.setattr(s.subprocess, "Popen",
                        lambda cmd, **kw: seen.update(kw=kw) or object())
    s._spawn(Config(opencode_bin="/x/o", timeout_s=10, project_root="/repo"))
    assert seen["kw"]["cwd"] == "/repo"


def test_linux_overlay_server_stays_in_owned_process_group(monkeypatch,tmp_path):
    from dataclasses import replace
    monkeypatch.setenv('JARVIS_REQUIRE_GUI','1')
    monkeypatch.setenv('SERVE_LOG',str(tmp_path/'serve.log'))
    spawned={}
    monkeypatch.setattr(serve.subprocess,'Popen',lambda argv,**kw:spawned.update(kw) or object())
    assert serve._spawn(replace(CFG,platform='linux'))
    assert spawned['start_new_session'] is False


def test_real_linux_supervised_server_exits_with_own_group(tmp_path):
    import os,signal,subprocess,sys,time
    from pathlib import Path
    if sys.platform!='linux':
        import pytest
        pytest.skip('Linux process-group lifecycle')
    marker=tmp_path/'server.pid'
    server=tmp_path/'opencode'
    server.write_text('#!'+sys.executable+'\nimport os,time\nfrom pathlib import Path\nPath('+repr(str(marker))+').write_text(str(os.getpid()))\ntime.sleep(60)\n')
    server.chmod(0o755)
    voice=Path(serve.__file__).parent
    code='import sys,time;sys.path.insert(0,'+repr(str(voice))+');from config import Config;import serve;assert serve._spawn(Config(platform="linux",timeout_s=5,opencode_bin='+repr(str(server))+',project_root='+repr(str(tmp_path))+'));time.sleep(60)'
    owner=subprocess.Popen([sys.executable,'-c',code],start_new_session=True,
        env=dict(os.environ,JARVIS_REQUIRE_GUI='1',SERVE_LOG=str(tmp_path/'server.log')))
    child=None
    def alive(pid):
        try:return Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[0]!='Z'
        except FileNotFoundError:return False
    try:
        deadline=time.monotonic()+4
        while not marker.exists() and time.monotonic()<deadline:time.sleep(.02)
        assert marker.exists()
        child=int(marker.read_text())
        assert os.getpgid(child)==owner.pid
        os.killpg(owner.pid,signal.SIGTERM)
        owner.wait(timeout=4)
        deadline=time.monotonic()+2
        while alive(child) and time.monotonic()<deadline:time.sleep(.02)
        assert not alive(child)
    finally:
        if owner.poll() is None:
            os.killpg(owner.pid,signal.SIGKILL);owner.wait(timeout=4)
        if child and alive(child):os.kill(child,signal.SIGKILL)


def test_linux_server_log_uses_private_xdg_state(monkeypatch,tmp_path):
    from dataclasses import replace
    import stat
    monkeypatch.delenv('SERVE_LOG',raising=False)
    monkeypatch.setenv('XDG_STATE_HOME',str(tmp_path/'estado ação'))
    monkeypatch.setattr(serve,'DEFAULT_LOG_PATH',str(tmp_path/'legacy/serve.log'))
    monkeypatch.setattr(serve.subprocess,'Popen',lambda *args,**kwargs:object())
    assert serve._spawn(replace(CFG,platform='linux'))
    path=tmp_path/'estado ação/jarvis/serve.log'
    assert path.is_file()
    assert stat.S_IMODE(path.stat().st_mode)==0o600
    assert not (tmp_path/'legacy').exists()


def test_linux_default_wait_accepts_cold_server_after_twenty_seconds(monkeypatch):
    from dataclasses import replace
    now = [0.0]
    monkeypatch.setattr(serve, '_spawn', lambda cfg: True)
    monkeypatch.setattr(serve.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(serve.time, 'sleep', lambda seconds: now.__setitem__(0, now[0] + seconds))
    monkeypatch.setattr(serve, 'is_healthy', lambda url: now[0] >= 21)
    assert serve.ensure_server(replace(CFG, platform='linux')) is True
    assert now[0] == 21


def test_linux_cold_start_still_has_a_bounded_deadline(monkeypatch):
    from dataclasses import replace
    now = [0.0]
    monkeypatch.setattr(serve, '_spawn', lambda cfg: True)
    monkeypatch.setattr(serve.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(serve.time, 'sleep', lambda seconds: now.__setitem__(0, now[0] + seconds))
    monkeypatch.setattr(serve, 'is_healthy', lambda url: False)
    assert serve.ensure_server(replace(CFG, platform='linux')) is False
    assert now[0] == 60


def test_explicit_startup_deadline_and_wsl_default_are_preserved(monkeypatch):
    from dataclasses import replace
    now = [0.0]
    monkeypatch.setattr(serve, '_spawn', lambda cfg: True)
    monkeypatch.setattr(serve.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(serve.time, 'sleep', lambda seconds: now.__setitem__(0, now[0] + seconds))
    monkeypatch.setattr(serve, 'is_healthy', lambda url: now[0] >= 21)
    assert serve.ensure_server(replace(CFG, platform='wsl')) is False
    assert now[0] == 20
    now[0] = 0
    assert serve.ensure_server(replace(CFG, platform='linux'), wait_s=3) is False
    assert now[0] == 3
