#!/bin/sh
# Upgrade a local Arch package in a disposable Arch Linux container.
set -eu
[ -f /.dockerenv ] || [ -f /run/.containerenv ] || { echo 'Execute apenas em container descartavel.' >&2; exit 2; }
task_old_package=${1:?pacote Arch anterior obrigatorio}
task_new_package=${2:?pacote Arch novo obrigatorio}
task_checks=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
. /etc/os-release
case "$ID" in
    arch) ;;
    *) echo 'O lifecycle de upgrade exige Arch Linux.' >&2; exit 2 ;;
esac
case "$(uname -m)" in
    x86_64) ;;
    *) echo 'O teste de upgrade Arch exige x86_64.' >&2; exit 2 ;;
esac
[ -f "$task_old_package" ] && [ -f "$task_new_package" ] || { echo 'Pacotes antigo e novo precisam existir.' >&2; exit 2; }

task_old_identity=$(pacman -Qp "$task_old_package")
task_new_identity=$(pacman -Qp "$task_new_package")
task_old_name=${task_old_identity%% *}
task_new_name=${task_new_identity%% *}
task_old_version=${task_old_identity#* }
task_new_version=${task_new_identity#* }
[ "$task_old_name" = jarvis-assistant ] && [ "$task_new_name" = "$task_old_name" ] || {
    echo 'Os dois pacotes precisam ser do Jarvis.' >&2
    exit 2
}
[ "$(vercmp "$task_new_version" "$task_old_version")" -gt 0 ] || {
    echo 'O pacote novo precisa ter uma versao superior.' >&2
    exit 2
}

# Arch's base image excludes documentation by default. The package records
# /usr/share/doc in its mtree, so disable that extraction filter for integrity checks.
sed -i '/^[[:space:]]*NoExtract[[:space:]]*=/d' /etc/pacman.conf
pacman -Syu --noconfirm --needed xorg-server-xvfb dbus
pacman -U --noconfirm "$task_old_package"
test "$(pacman -Q "$task_old_name")" = "$task_old_identity"
jarvis --doctor

umask 077
task_state=$(mktemp -d)
trap 'rm -rf "$task_state" "$task_state.sha256"' EXIT HUP INT TERM
export XDG_DATA_HOME="$task_state/data" XDG_CONFIG_HOME="$task_state/config" XDG_CACHE_HOME="$task_state/cache"
mkdir -p "$XDG_DATA_HOME/jarvis/models" "$XDG_CONFIG_HOME/jarvis" "$XDG_CACHE_HOME/jarvis"
printf '%s\n' '{"language":"pt","fixture":"preserve Arch upgrade"}' > "$XDG_CONFIG_HOME/jarvis/settings.json"
dd if=/dev/urandom of="$XDG_DATA_HOME/jarvis/models/opaque-user-data.bin" bs=1024 count=8 2>/dev/null
printf '%s\n' cache-fixture > "$XDG_CACHE_HOME/jarvis/cache-sentinel"
find "$task_state" -type f -exec sha256sum '{}' \; > "$task_state.sha256"

pacman -U --noconfirm "$task_new_package"
test "$(pacman -Q "$task_new_name")" = "$task_new_identity"
sha256sum -c "$task_state.sha256"
jarvis --doctor
pacman -Qkk jarvis-assistant
sh "$task_checks/test-native-package.sh" arch "$task_new_package"
sha256sum -c "$task_state.sha256"
! pacman -Q jarvis-assistant >/dev/null 2>&1
printf '%s\n' 'PASS: Arch package upgrade, installed runtime/integrity, removal and unchanged config/model-data/cache hashes'
