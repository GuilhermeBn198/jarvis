"""Read-only diagnostics. Presence is distinct from runtime validation."""
import importlib.util
import os
import shutil
import subprocess
from pathlib import Path
from platforms import desktop_session


def _ffmpeg_has_audio_input(config) -> bool:
    try:
        result = subprocess.run(
            [config.ffmpeg_exe, '-hide_banner', '-demuxers'],
            capture_output=True, text=True, errors='replace', timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if result.returncode != 0:
        return False
    for line in (result.stdout + '\n' + result.stderr).splitlines():
        fields = line.split()
        if len(fields) > 1 and fields[0].startswith('D') and config.audio_backend in fields[1:4]:
            return True
    return False


def _ffmpeg_lists_audio_sources(config) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [config.ffmpeg_exe, '-hide_banner', '-sources', config.audio_backend],
            capture_output=True, text=True, errors='replace', timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    output = result.stdout + '\n' + result.stderr
    if result.returncode != 0:
        return False, output.strip()[-200:]
    if 'Cannot list sources:' in output:
        return False, output.strip()[-200:]
    header = f'Auto-detected sources for {config.audio_backend}:'
    if header not in output:
        return False, 'FFmpeg nao retornou a lista de fontes do backend'
    sources = [line for line in output.split(header, 1)[1].splitlines() if line.strip()]
    if not sources:
        return False, 'nenhuma fonte de audio foi enumerada'
    return True, ''


def _capture_capability(config, ffmpeg_available: bool) -> dict:
    capability = {'available': False, 'backend': config.audio_backend}
    if not ffmpeg_available:
        capability['reason'] = 'ffmpeg ausente'
        return capability
    if config.platform != 'linux':
        capability.update(available=True, reason='ffmpeg presente; gravacao real ainda nao testada')
        return capability
    if not _ffmpeg_has_audio_input(config):
        capability['reason'] = f'ffmpeg nao disponibiliza entrada {config.audio_backend}'
        return capability
    available, detail = _ffmpeg_lists_audio_sources(config)
    if not available:
        capability['reason'] = f'ffmpeg nao conseguiu enumerar fontes {config.audio_backend}: {detail}'
        return capability
    capability.update(
        available=True,
        reason='ffmpeg enumera fontes de audio; gravacao real ainda nao testada',
    )
    return capability


def _desktop_capability(config, session: str) -> dict:
    capability = {'available': False, 'backend': session, 'validation': 'not_run'}
    if config.platform != 'linux':
        capability['reason'] = 'backend Windows exige validacao de runtime'
        return capability
    if session == 'headless':
        capability['reason'] = 'sem sessao grafica'
        return capability
    if session == 'wayland':
        if importlib.util.find_spec('dbus_next') is None:
            capability['reason'] = 'dbus-next ausente no runtime Python do Jarvis'
            return capability
        eis_available, eis_reason = _eis_input_status()
        capability.update(
            available=True,
            authorization_required=True,
            reason='backend Wayland disponivel; o portal exige autorizacao do usuario para captura e controle; runtime ainda nao validado',
            eis_input_available=eis_available,
            eis_input_reason=eis_reason,
        )
        return capability
    if session == 'x11':
        xdotool = shutil.which('xdotool')
        capability.update(
            available=xdotool is not None,
            authorization_required=False,
            reason='xdotool encontrado; entrada e acessibilidade ainda nao validadas' if xdotool else 'xdotool ausente',
        )
        return capability
    capability['reason'] = 'sessao grafica desconhecida'
    return capability


def _eis_input_status() -> tuple[bool, str]:
    if importlib.util.find_spec('libei') is None:
        return False, 'python-libei ausente; cliques usam fallback RemoteDesktop'
    try:
        from libei import ei, portal
        if not ei.is_available():
            return False, 'biblioteca nativa libei ausente; cliques usam fallback RemoteDesktop'
        if not portal.is_available():
            return False, 'PyGObject/Gio ausente; cliques usam fallback RemoteDesktop'
    except Exception as exc:
        return False, f'libei/EIS indisponivel ({exc}); cliques usam fallback RemoteDesktop'
    return True, 'libei/EIS disponivel; a sessao exige autorizacao do portal'


def diagnose(config) -> dict:
    session = desktop_session(os.environ)
    dependencies = {}
    for name, executable in [('ffmpeg', config.ffmpeg_exe), ('ffplay', config.ffplay_exe),
                             ('piper', config.piper_exe), ('opencode', config.opencode_bin)]:
        found = shutil.which(executable)
        dependencies[name] = {'available': found is not None, 'path': found,
                              'reason': 'encontrado; runtime nao verificado' if found else f'executavel ausente: {executable}'}
    model = Path(config.piper_model)
    model_exists = model.is_file() and Path(str(model) + '.json').is_file()
    dependencies['piper_model'] = {'available': model_exists, 'path': str(model),
                                  'reason': 'modelo e configuracao presentes' if model_exists else 'modelo .onnx ou configuracao .onnx.json ausente'}
    capabilities = {
        'capture': _capture_capability(config, dependencies['ffmpeg']['available']),
        'tts': {'available': dependencies['piper']['available'] and model_exists and dependencies['ffplay']['available'],
                'backend': config.tts_backend, 'reason': 'presenca de dependencias; sintese nao verificada'},
        'desktop': _desktop_capability(config, session),
    }
    if config.tts_backend == 'sapi':
        found = shutil.which(config.powershell_exe)
        capabilities['tts'] = {'available': found is not None, 'backend': 'sapi', 'reason': 'SAPI exige teste de runtime Windows'}
    return {'project_root': config.project_root, 'platform': config.platform, 'session': session, 'dependencies': dependencies,
            'capabilities': capabilities}
