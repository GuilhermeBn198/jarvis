#!/bin/sh
# Upgrade a local DEB in a disposable Debian/Ubuntu container.
set -eu
[ -f /.dockerenv ] || [ -f /run/.containerenv ] || { echo 'Execute apenas em container descartavel.' >&2; exit 2; }
task_family=${1:?familia obrigatoria}
task_old_package=${2:?DEB anterior obrigatorio}
task_new_package=${3:?DEB novo obrigatorio}
task_checks=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
. /etc/os-release
case "$task_family:$ID" in
    debian:debian|ubuntu:ubuntu) ;;
    *) echo 'Familia e ambiente nao correspondem.' >&2; exit 2 ;;
esac

task_old_version=$(dpkg-deb -f "$task_old_package" Version)
task_new_version=$(dpkg-deb -f "$task_new_package" Version)
dpkg --compare-versions "$task_new_version" gt "$task_old_version" || {
    echo 'O DEB novo precisa ter uma versao superior.' >&2
    exit 2
}

apt-get update
apt-get install -y --no-install-recommends \
    -o 'Dpkg::Options::=--path-include=/usr/share/doc/*' \
    "$task_old_package" xvfb dbus-daemon
test "$(dpkg-query -W -f='${Version}' jarvis-assistant)" = "$task_old_version"
jarvis --doctor
test "$(/usr/lib/jarvis/bin/opencode --version)" = '1.18.23'

umask 077
task_state=$(mktemp -d)
export XDG_DATA_HOME="$task_state/data" XDG_CONFIG_HOME="$task_state/config" XDG_CACHE_HOME="$task_state/cache"
mkdir -p "$XDG_DATA_HOME/jarvis/models" "$XDG_CONFIG_HOME/jarvis" "$XDG_CACHE_HOME/jarvis"
printf '%s\n' '{"language":"pt","fixture":"preserve deb upgrade"}' > "$XDG_CONFIG_HOME/jarvis/settings.json"
dd if=/dev/urandom of="$XDG_DATA_HOME/jarvis/models/opaque-user-data.bin" bs=1024 count=8 2>/dev/null
printf '%s\n' cache-fixture > "$XDG_CACHE_HOME/jarvis/cache-sentinel"
find "$task_state" -type f -exec sha256sum '{}' \; > "$task_state.sha256"

apt-get install -y --no-install-recommends \
    -o 'Dpkg::Options::=--path-include=/usr/share/doc/*' "$task_new_package"
test "$(dpkg-query -W -f='${Version}' jarvis-assistant)" = "$task_new_version"
sha256sum -c "$task_state.sha256"
jarvis --doctor
sh "$task_checks/test-native-package.sh" "$task_family" "$task_new_package"
sha256sum -c "$task_state.sha256"
! dpkg-query -W -f='${Status}' jarvis-assistant 2>/dev/null | grep -q 'install ok installed'
printf '%s\n' 'PASS: DEB upgrade, installed runtime/GUI/integrity, removal and unchanged config/model-data/cache fixture hashes'
