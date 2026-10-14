import subprocess
from pathlib import Path
import pytest
from config import load_config
from linux_screen import screenshot, copy_portal_image
from tts import VoiceError


def test_portal_uri_preserves_unicode(tmp_path):
    source = tmp_path / 'captura ação.png'
    source.write_bytes(b'\x89PNG\r\n\x1a\ncontent')
    destination = tmp_path / 'output.png'
    assert copy_portal_image(source.as_uri(), str(destination)) == str(destination)
    assert destination.read_bytes() == source.read_bytes()
    assert source.exists()


@pytest.mark.parametrize('uri', ['https://example.com/a.png', 'file://remote/a.png', 'file:///missing.png'])
def test_invalid_portal_image_rejected(uri, tmp_path):
    with pytest.raises(VoiceError):
        copy_portal_image(uri, str(tmp_path / 'out.png'))


def test_wayland_uses_portal_not_xwayland(monkeypatch, tmp_path):
    import linux_screen
    source=tmp_path / 'portal.png'
    source.write_bytes(b'\x89PNG\r\n\x1a\nimage')
    class Portal:
        def request(self, interface, method, args, timeout_s):
            assert interface == 'org.freedesktop.portal.Screenshot'
            assert method == 'Screenshot'
            return {'uri': source.as_uri()}
    monkeypatch.setattr(linux_screen, 'PortalClient', Portal)
    monkeypatch.setenv('XDG_SESSION_TYPE', 'wayland')
    monkeypatch.setenv('DISPLAY', ':0')
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: pytest.fail('must not invoke X11 ffmpeg'))
    cfg=load_config({'JARVIS_PLATFORM':'linux'})
    output=tmp_path / 'out.png'
    assert screenshot(str(output),cfg)==str(output)


def test_x11_failure_does_not_return_old_image(monkeypatch,tmp_path):
    monkeypatch.setenv('XDG_SESSION_TYPE','x11')
    monkeypatch.delenv('WAYLAND_DISPLAY',raising=False)
    monkeypatch.setenv('DISPLAY',':0')
    import linux_screen
    monkeypatch.setattr(linux_screen,'x11_dimensions',lambda display:(1920,1080))
    def run(argv, **kw):
        assert 'x11grab' in argv
        return subprocess.CompletedProcess(argv,1,'','cannot open display')
    monkeypatch.setattr(subprocess,'run',run)
    output=tmp_path/'stale.png'
    output.write_bytes(b'old')
    with pytest.raises(VoiceError,match='display'):
        screenshot(str(output),load_config({'JARVIS_PLATFORM':'linux'}))


def test_headless_is_explicit(monkeypatch,tmp_path):
    for key in ('DISPLAY','WAYLAND_DISPLAY','XDG_SESSION_TYPE'):
        monkeypatch.delenv(key,raising=False)
    with pytest.raises(VoiceError,match='sessao grafica'):
        screenshot(str(tmp_path/'out.png'),load_config({'JARVIS_PLATFORM':'linux'}))


def test_x11_captures_full_root_size(monkeypatch,tmp_path):
    import linux_screen
    monkeypatch.setenv('XDG_SESSION_TYPE','x11')
    monkeypatch.delenv('WAYLAND_DISPLAY',raising=False)
    monkeypatch.setenv('DISPLAY',':0')
    monkeypatch.setattr(linux_screen,'x11_dimensions',lambda display:(3840,1080))
    def run(argv,**kw):
        assert argv[argv.index('-video_size')+1]=='3840x1080'
        Path(argv[-1]).write_bytes(b'\x89PNG\r\n\x1a\nimage')
        return subprocess.CompletedProcess(argv,0,'','')
    monkeypatch.setattr(subprocess,'run',run)
    assert screenshot(str(tmp_path/'out.png'),load_config({'JARVIS_PLATFORM':'linux'}))==str(tmp_path/'out.png')
