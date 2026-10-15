#!/bin/sh
# Destructive package lifecycle checks: disposable containers only.
set -eu
[ -f /.dockerenv ] || [ -f /run/.containerenv ] || { echo 'Execute apenas em container descartavel.' >&2; exit 2; }
task_family=${1:?familia obrigatoria}
task_package=${2:?artefato obrigatorio}
. /etc/os-release
task_user_data=$(mktemp -d)
export XDG_DATA_HOME=$task_user_data
export PYTHONDONTWRITEBYTECODE=1
mkdir -p "$XDG_DATA_HOME/jarvis"
printf '%s\n' preserved > "$XDG_DATA_HOME/jarvis/package-test"
case "$task_family:$ID" in
    debian:debian) apt-get update; apt-get install -y --no-install-recommends -o "Dpkg::Options::=--path-include=/usr/share/doc/*" "$task_package" ;;
    fedora:fedora) dnf install -y --setopt=install_weak_deps=False "$task_package" ;;
    arch:arch) sed -i '/^NoExtract/d' /etc/pacman.conf; pacman -Syu --noconfirm; pacman -U --noconfirm "$task_package" ;;
    *) echo 'Familia e ambiente nao correspondem.' >&2; exit 2 ;;
esac
test "$(cat "$XDG_DATA_HOME/jarvis/package-test")" = preserved
jarvis --doctor
[ "$(/usr/lib/jarvis/bin/opencode --version)" = '1.18.23' ]
PYTHONPATH=/usr/lib/jarvis/python python3 - <<'PY'
from pathlib import Path
import importlib,gi,platform
root=Path('/usr/lib/jarvis')
expected={'x86_64':62,'aarch64':183}[platform.machine()]
for binary in (Path('/usr/bin/jarvis-overlay'),root/'bin/opencode'):
    with binary.open('rb') as stream:header=stream.read(20)
    assert header[:4]==b'\x7fELF' and int.from_bytes(header[18:20],'little')==expected,binary
for relative in ('voice/loop.py','voice/triggers.json','jarvis',
                 'mcp_servers/win_context/server.py','mcp_servers/delegate_local/server.py',
                 '.opencode/plugins/act-tools.ts','.opencode/package-lock.json'):
    assert (root/relative).is_file(),relative
for name in ('faster_whisper','piper','mcp','httpx','dbus_next'):
    module=importlib.import_module(name)
    assert Path(module.__file__).resolve().is_relative_to(root/'python'),name
# AT-SPI is intentionally supplied by the distribution's GI/typelib packages.
gi.require_version('Atspi','2.0')
from gi.repository import Atspi
print('Private runtime, resources and AT-SPI typelib passed')
PY
for task_tool in ffmpeg ffplay pactl arecord xdotool wl-paste xclip; do command -v "$task_tool"; done
ffmpeg -version >/dev/null
ffplay -version >/dev/null
pactl --version
case "$task_family" in
    debian)
        task_verify_status=0
        task_verify=$(dpkg -V jarvis-assistant) || task_verify_status=$?
        printf '%s\n' "$task_verify"
        test "$task_verify_status" -eq 0
        test -z "$task_verify"
        apt-get remove -y jarvis-assistant
        ;;
    fedora) rpm -V jarvis-assistant; dnf remove -y jarvis-assistant ;;
    arch) pacman -Qkk jarvis-assistant; pacman -R --noconfirm jarvis-assistant ;;
esac
test ! -e /usr/bin/jarvis
test ! -e /usr/bin/jarvis-overlay
test ! -e /usr/lib/jarvis
test "$(cat "$XDG_DATA_HOME/jarvis/package-test")" = preserved
printf '%s\n' 'PASS: package install/resources/imports/integrity/remove/data preservation (headless only)'
