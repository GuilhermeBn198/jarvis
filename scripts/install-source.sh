#!/bin/sh
# Unprivileged source install; system libraries remain owned by the distro.
set -eu
task_root=$(CDPATH= cd -P "$(dirname "$0")/.." && pwd)
task_prefix=
task_python=${JARVIS_PYTHON:-python3}
task_overlay=$task_root/gui/src-tauri/target/release/jarvis-overlay
task_deps=1
task_autostart=0
task_voice=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --prefix) [ "$#" -ge 2 ]; task_prefix=$2; shift 2 ;;
        --overlay) [ "$#" -ge 2 ]; task_overlay=$2; shift 2 ;;
        --no-deps) task_deps=0; shift ;;
        --autostart) task_autostart=1; shift ;;
        --download-voice) task_voice=1; shift ;;
        --help) echo 'Uso: install-source.sh [--prefix DIR] [--overlay BIN] [--no-deps] [--autostart] [--download-voice]'; exit 0 ;;
        *) echo "opcao desconhecida: $1" >&2; exit 2 ;;
    esac
done
if [ "$task_deps" -eq 1 ] && [ "$(id -u)" -eq 0 ]; then
    echo 'Instalacao por fonte com dependencias requer usuario comum; use pacote nativo para instalar no sistema.' >&2
    exit 1
fi
if [ -z "$task_prefix" ]; then
    [ -n "${HOME:-}" ] || { echo 'Informe --prefix ou HOME.' >&2; exit 2; }
    task_prefix=$HOME/.local
fi
command -v "$task_python" >/dev/null
"$task_python" -c 'import sys; assert sys.version_info >= (3,10), "Python 3.10+ necessario"' 
if [ "$task_deps" -eq 1 ]; then command -v npm >/dev/null; fi
"$task_python" "$task_root/scripts/stage-linux.py" --prefix "$task_prefix" --overlay "$task_overlay"
task_app=$task_prefix/lib/jarvis
if [ "$task_deps" -eq 1 ]; then
    "$task_python" -m venv --system-site-packages "$task_app/voice/.venv"
    "$task_app/voice/.venv/bin/python" -m pip install -r "$task_app/voice/requirements-linux.txt" \
        -r "$task_app/mcp_servers/win_context/requirements.txt" \
        -r "$task_app/mcp_servers/delegate_local/requirements.txt"
    npm ci --prefix "$task_app/.opencode" --ignore-scripts
fi
# User installation may live outside the GUI session's PATH; use quoted Exec.
"$task_python" - "$task_prefix" <<'PY'
import sys
from pathlib import Path
prefix=Path(sys.argv[1])
path=prefix/'share/applications/com.jarvis.overlay.desktop'
executable=str(prefix/'bin/jarvis-overlay').replace('\\','\\\\').replace('"','\\"').replace('$','\\$').replace('`','\\`')
path.write_text(path.read_text().replace('Exec=jarvis-overlay',f'Exec="{executable}"'))
PY
if [ "$task_voice" -eq 1 ]; then "$task_prefix/bin/jarvis" --download-voice; fi
if [ "$task_autostart" -eq 1 ]; then
    task_config=${XDG_CONFIG_HOME:-${HOME}/.config}
    case "$task_config" in /*) ;; *) task_config=${HOME}/.config ;; esac
    mkdir -p "$task_config/autostart"
    cp "$task_prefix/share/applications/com.jarvis.overlay.desktop" "$task_config/autostart/com.jarvis.overlay.desktop"
fi
echo "Instalado em $task_prefix. Diagnostico: $task_prefix/bin/jarvis --doctor"
echo "Configure o agente opencode e a voz Piper antes de iniciar o loop. Veja $task_prefix/share/doc/jarvis/linux.md."
