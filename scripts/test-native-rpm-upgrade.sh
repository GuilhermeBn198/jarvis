#!/bin/sh
# Upgrade a local RPM in a disposable Fedora/openSUSE/RHEL-family container.
set -eu
[ -f /.dockerenv ] || [ -f /run/.containerenv ] || { echo 'Execute apenas em container descartavel.' >&2; exit 2; }
task_family=${1:?familia obrigatoria}
task_old_package=${2:?RPM anterior obrigatorio}
task_new_package=${3:?RPM novo obrigatorio}
task_checks=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
. /etc/os-release
case "$task_family:$ID" in
    fedora:fedora) task_manager=fedora ;;
    suse:opensuse-tumbleweed) task_manager=suse ;;
    rhel:rhel|rhel:almalinux|rhel:rocky|rhel:centos|rhel:ol)
        [ "${VERSION_ID%%.*}" = 10 ] || { echo 'Teste RHEL exige versao 10.' >&2; exit 2; }
        task_manager=rhel
        ;;
    *) echo 'Familia e ambiente nao correspondem.' >&2; exit 2 ;;
esac

task_old_version=$(rpm -qp --qf '%{VERSION}' "$task_old_package")
task_new_version=$(rpm -qp --qf '%{VERSION}' "$task_new_package")
task_old_release=$(rpm -qp --qf '%{RELEASE}' "$task_old_package")
task_new_release=$(rpm -qp --qf '%{RELEASE}' "$task_new_package")
[ "$task_old_version" = "$task_new_version" ] || { echo 'As revisoes precisam ter a mesma versao upstream.' >&2; exit 2; }
case "$task_old_release:$task_new_release" in
    1*:2*) ;;
    *) echo 'O RPM novo precisa ter release 2 e o anterior release 1.' >&2; exit 2 ;;
esac

umask 077
task_state=$(mktemp -d)
export XDG_DATA_HOME="$task_state/data" XDG_CONFIG_HOME="$task_state/config" XDG_CACHE_HOME="$task_state/cache"
mkdir -p "$XDG_DATA_HOME/jarvis/models" "$XDG_CONFIG_HOME/jarvis" "$XDG_CACHE_HOME/jarvis"
printf '%s\n' '{"language":"pt","fixture":"preserve RPM upgrade"}' > "$XDG_CONFIG_HOME/jarvis/settings.json"
dd if=/dev/urandom of="$XDG_DATA_HOME/jarvis/models/opaque-user-data.bin" bs=1024 count=8 2>/dev/null
printf '%s\n' cache-fixture > "$XDG_CACHE_HOME/jarvis/cache-sentinel"
sha256sum "$XDG_CONFIG_HOME/jarvis/settings.json" \
    "$XDG_DATA_HOME/jarvis/models/opaque-user-data.bin" \
    "$XDG_CACHE_HOME/jarvis/cache-sentinel" > "$task_state.sha256"

case "$task_manager" in
    fedora)
        dnf install -y --setopt=install_weak_deps=False xorg-x11-server-Xvfb dbus-daemon "$task_old_package"
        test "$(rpm -q --qf '%{RELEASE}' jarvis-assistant)" = "$task_old_release"
        sha256sum -c "$task_state.sha256"
        jarvis --doctor
        dnf upgrade -y --setopt=install_weak_deps=False "$task_new_package"
        ;;
    suse)
        zypper --non-interactive install --no-recommends --allow-unsigned-rpm \
            xorg-x11-server-Xvfb dbus-1-daemon "$task_old_package"
        test "$(rpm -q --qf '%{RELEASE}' jarvis-assistant)" = "$task_old_release"
        sha256sum -c "$task_state.sha256"
        jarvis --doctor
        zypper --non-interactive install --no-recommends --allow-unsigned-rpm "$task_new_package"
        ;;
    rhel)
        dnf install -y epel-release dnf-plugins-core
        dnf config-manager --set-enabled crb
        task_helpers=0
        for task_extra in "$(dirname "$task_old_package")"/xdotool-*."$(uname -m)".rpm; do
            [ -f "$task_extra" ] || continue
            task_helper=$task_extra
            task_helpers=$((task_helpers+1))
        done
        [ "$task_helpers" -eq 1 ] || { echo 'Forneca exatamente um RPM xdotool da arquitetura do alvo.' >&2; exit 2; }
        dnf install -y --setopt=install_weak_deps=False \
            "$task_helper" "$task_old_package" weston xwayland-run dbus-daemon mesa-libEGL mesa-dri-drivers
        test "$(rpm -q --qf '%{RELEASE}' jarvis-assistant)" = "$task_old_release"
        sha256sum -c "$task_state.sha256"
        jarvis --doctor
        dnf upgrade -y --setopt=install_weak_deps=False "$task_new_package"
        ;;
esac

test "$(rpm -q --qf '%{RELEASE}' jarvis-assistant)" = "$task_new_release"
sha256sum -c "$task_state.sha256"
jarvis --doctor
rpm -V jarvis-assistant
sh "$task_checks/test-native-package.sh" "$task_family" "$task_new_package"
sha256sum -c "$task_state.sha256"
! rpm -q jarvis-assistant
printf '%s\n' 'PASS: RPM upgrade, installed runtime/GUI/integrity, removal and unchanged config/model-data/cache fixture hashes'
