"""Screenshot backends; Wayland always uses consent mediated by a portal."""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse, unquote
from platforms import desktop_session
from portal import PortalClient
from tts import VoiceError

PNG_HEADER = b'\x89PNG\r\n\x1a\n'


def copy_portal_image(uri: str, out_path: str) -> str:
    parsed = urlparse(uri)
    if parsed.scheme != 'file' or parsed.netloc not in ('', 'localhost'):
        raise VoiceError('portal retornou URI nao local')
    source = Path(unquote(parsed.path))
    output = Path(out_path)
    try:
        with source.open('rb') as stream:
            if stream.read(8) != PNG_HEADER:
                raise VoiceError('portal nao retornou imagem PNG valida')
            stream.seek(0)
            output.parent.mkdir(parents=True, exist_ok=True)
            fd, staged = tempfile.mkstemp(prefix='.jarvis-shot-', dir=output.parent)
            try:
                with os.fdopen(fd, 'wb') as target:
                    shutil.copyfileobj(stream, target)
                os.replace(staged, output)
            finally:
                Path(staged).unlink(missing_ok=True)
    except OSError as exc:
        raise VoiceError(f'falha ao ler captura do portal: {exc}') from exc
    return str(output)



def x11_dimensions(display: str) -> tuple[int, int]:
    import ctypes
    from ctypes.util import find_library
    library = find_library("X11")
    if not library:
        raise VoiceError("captura X11 exige libX11")
    x11 = ctypes.CDLL(library)
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XDefaultScreen.argtypes = [ctypes.c_void_p]
    x11.XDefaultScreen.restype = ctypes.c_int
    for name in ("XDisplayWidth", "XDisplayHeight"):
        fn = getattr(x11, name)
        fn.argtypes = [ctypes.c_void_p, ctypes.c_int]
        fn.restype = ctypes.c_int
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    x11.XCloseDisplay.restype = ctypes.c_int
    connection = x11.XOpenDisplay(display.encode())
    if not connection:
        raise VoiceError(f"nao foi possivel abrir display X11: {display}")
    try:
        screen = x11.XDefaultScreen(connection)
        return x11.XDisplayWidth(connection, screen), x11.XDisplayHeight(connection, screen)
    finally:
        x11.XCloseDisplay(connection)


def screenshot(out_path: str, cfg) -> str:
    session = desktop_session(os.environ)
    if session == 'headless':
        raise VoiceError('captura exige sessao grafica X11 ou Wayland')
    if session == 'wayland':
        response = PortalClient().request('org.freedesktop.portal.Screenshot', 'Screenshot',
                                        ('', {'interactive': True}), timeout_s=60)
        uri = response.get('uri')
        if not isinstance(uri, str):
            raise VoiceError('portal nao retornou URI da captura')
        return copy_portal_image(uri, out_path)
    output = Path(out_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, staged = tempfile.mkstemp(prefix='.jarvis-shot-', suffix='.png', dir=output.parent)
    os.close(fd)
    try:
        width, height = x11_dimensions(os.environ["DISPLAY"])
        argv = [cfg.ffmpeg_exe, '-hide_banner', '-loglevel', 'error', '-f', 'x11grab',
                '-video_size', f'{width}x{height}', '-i', os.environ['DISPLAY'], '-frames:v', '1', '-y', staged]
        result = subprocess.run(argv, capture_output=True, text=True, errors='replace', timeout=30)
        if result.returncode:
            raise VoiceError(f'captura X11 falhou: {result.stderr.strip()[-200:]}')
        with open(staged, 'rb') as stream:
            if stream.read(8) != PNG_HEADER:
                raise VoiceError('captura X11 nao produziu PNG valido')
        os.replace(staged, output)
        return str(output)
    except (OSError, subprocess.SubprocessError) as exc:
        raise VoiceError(f'falha ao capturar tela X11: {exc}') from exc
    finally:
        Path(staged).unlink(missing_ok=True)
