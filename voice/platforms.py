"""Platform and XDG selection, without importing hardware dependencies."""
import os
import platform as host_platform
import sys
from pathlib import Path


def detect_platform(env: dict, release: str) -> str:
    override = env.get('JARVIS_PLATFORM', '').strip().lower()
    if override:
        if override not in ('linux', 'windows', 'wsl'):
            raise ValueError('JARVIS_PLATFORM deve ser linux, windows ou wsl')
        return override
    if sys.platform == 'win32':
        return 'windows'
    if 'microsoft' in release.lower() or env.get('WSL_INTEROP') or env.get('WSL_DISTRO_NAME'):
        return 'wsl'
    if sys.platform.startswith('linux'):
        return 'linux'
    raise ValueError(f'plataforma nao suportada: {sys.platform}')


def current_platform(env: dict | None = None) -> str:
    return detect_platform(os.environ if env is None else env, host_platform.release())


def desktop_session(env: dict) -> str:
    if env.get('XDG_SESSION_TYPE') == 'wayland' or env.get('WAYLAND_DISPLAY'):
        return 'wayland'
    if env.get('DISPLAY'):
        return 'x11'
    return 'headless'


def xdg_path(kind: str, env: dict) -> Path:
    home = Path(env.get('HOME') or Path.home())
    defaults = {'config': home / '.config', 'data': home / '.local/share',
                'cache': home / '.cache', 'state': home / '.local/state'}
    if kind == 'runtime':
        value = env.get('XDG_RUNTIME_DIR')
        if not value or not Path(value).is_absolute():
            raise ValueError('XDG_RUNTIME_DIR absoluto necessario')
        return Path(value) / 'jarvis'
    if kind not in defaults:
        raise ValueError(f'tipo XDG invalido: {kind}')
    value = env.get(f'XDG_{kind.upper()}_HOME', '')
    base = Path(value) if value and Path(value).is_absolute() else defaults[kind]
    return base / 'jarvis'
