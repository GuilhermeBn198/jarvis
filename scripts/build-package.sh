#!/bin/sh
# Explicit native target; fail if the target's package tools are unavailable.
set -eu
task_root=$(CDPATH= cd -P "$(dirname "$0")/.." && pwd)
task_target=
task_arch=$(uname -m)
task_output=$task_root/dist/native
while [ "$#" -gt 0 ]; do
    case "$1" in
        --target) task_target=$2; shift 2 ;;
        --arch) task_arch=$2; shift 2 ;;
        --output) task_output=$2; shift 2 ;;
        --help) echo 'Uso: build-package.sh --target ALVO --arch ARQUITETURA [--output DIR]'; exit 0 ;;
        *) echo "opcao desconhecida: $1" >&2; exit 2 ;;
    esac
done
if [ "$task_arch" != "$(uname -m)" ]; then
    echo 'Build nativo exige arquitetura correspondente; use container/VM do alvo.' >&2
    exit 2
fi
mkdir -p "$task_output"
task_output=$(CDPATH= cd -P "$task_output" && pwd)
case "$task_target" in
    void-glibc)
        . /etc/os-release
        [ "$ID" = void ] || { echo 'Alvo void-glibc exige ambiente Void Linux.' >&2; exit 2; }
        [ "$(xbps-uhelper arch)" = "$task_arch" ] || { echo 'Alvo void-glibc exige libc glibc nativa.' >&2; exit 2; }
        task_build=$(mktemp -d)
        task_collection=${JARVIS_VOID_PACKAGES:-$task_build/void-packages}
        task_void_commit=dbf843f5f1dad63846b6d147ec10662cf8e8078a
        if [ ! -d "$task_collection" ]; then
            git init -q "$task_collection"
            git -C "$task_collection" remote add origin https://github.com/void-linux/void-packages.git
            git -C "$task_collection" fetch --depth 1 origin "$task_void_commit"
            git -C "$task_collection" checkout --detach FETCH_HEAD
        fi
        [ "$(git -C "$task_collection" rev-parse HEAD)" = "$task_void_commit" ] || { echo 'A colecao Void deve corresponder ao commit fixado da receita.' >&2; exit 2; }
        task_collection=$(CDPATH= cd -P "$task_collection" && pwd)
        task_template=$task_collection/srcpkgs/jarvis-assistant
        [ ! -e "$task_template" ] || { echo 'Use uma colecao sem receita Jarvis preexistente.' >&2; exit 2; }
        mkdir -p "$task_template/files"
        python3 "$task_root/scripts/source-archive.py" --output "$task_template/files/jarvis-0.1.0.tar.gz"
        python3 - "$task_root/packaging/void/template" "$task_template" <<'PY'
from pathlib import Path
import hashlib,sys
source=Path(sys.argv[1]);target=Path(sys.argv[2])
with (target/'files/jarvis-0.1.0.tar.gz').open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
(target/'template').write_text(source.read_text().replace('@JARVIS_SOURCE_SHA256@',digest))
PY
        (cd "$task_collection" && ./xbps-src -j2 pkg jarvis-assistant)
        find "$task_collection/hostdir/binpkgs" -type f -name "jarvis-assistant-*.$task_arch.xbps" -exec cp '{}' "$task_output/" \;
        ;;
    alpine)
        . /etc/os-release
        [ "$ID" = 'alpine' ] || { echo 'Alvo alpine exige ambiente Alpine.' >&2; exit 2; }
        command -v abuild >/dev/null
        [ "$(id -u)" -ne 0 ] || { echo 'Execute abuild com usuario de build, sem root.' >&2; exit 2; }
        task_build=$(mktemp -d "$task_output/.alpine-build-XXXXXX")
        python3 "$task_root/scripts/source-archive.py" --output "$task_build/jarvis-0.1.0.tar.gz"
        cp "$task_root/packaging/alpine/APKBUILD" "$task_build/APKBUILD"
        export REPODEST=$task_output
        cd "$task_build"
        abuild checksum
        abuild -r
        ;;
    debian|ubuntu)
        . /etc/os-release
        case "$task_target:$ID" in
            debian:debian|ubuntu:ubuntu) ;;
            debian:*) echo 'Alvo debian exige ambiente Debian.' >&2; exit 2 ;;
            ubuntu:*) echo 'Alvo ubuntu exige ambiente Ubuntu.' >&2; exit 2 ;;
        esac
        command -v dpkg-buildpackage >/dev/null
        task_build=$(mktemp -d "$task_output/.$task_target-build-XXXXXX")
        python3 "$task_root/scripts/source-archive.py" --output "$task_build/jarvis-0.1.0.tar.gz"
        tar -xzf "$task_build/jarvis-0.1.0.tar.gz" -C "$task_build"
        cd "$task_build/jarvis-0.1.0"
        cp -a packaging/debian debian
        dpkg-buildpackage -us -uc -b
        find "$task_build" -maxdepth 1 -name '*.deb' -type f -exec cp '{}' "$task_output/" \;
        ;;
    fedora|suse|rhel)
        . /etc/os-release
        case "$task_target:$ID" in
            fedora:fedora|suse:opensuse-tumbleweed) ;;
            fedora:*) echo 'Alvo fedora exige ambiente Fedora.' >&2; exit 2 ;;
            suse:*) echo 'Alvo suse exige openSUSE Tumbleweed.' >&2; exit 2 ;;
            rhel:rhel|rhel:almalinux|rhel:rocky|rhel:centos|rhel:ol)
                [ "${VERSION_ID%%.*}" = '10' ] || { echo 'Alvo rhel exige ambiente RHEL 10 ou derivado.' >&2; exit 2; }
                ;;
            rhel:*) echo 'Alvo rhel exige ambiente RHEL 10 ou derivado.' >&2; exit 2 ;;
        esac
        command -v rpmbuild >/dev/null
        task_build=$(mktemp -d "$task_output/.$task_target-build-XXXXXX")
        mkdir -p "$task_build/SOURCES" "$task_build/SPECS"
        python3 "$task_root/scripts/source-archive.py" --output "$task_build/SOURCES/jarvis-0.1.0.tar.gz"
        cp "$task_root/packaging/rpm/$task_target/jarvis-assistant.spec" "$task_build/SPECS/"
        if [ "$task_target" = 'rhel' ]; then
            # EPEL 10 lacks xdotool. Build its native RPM alongside Jarvis.
            task_xdotool_commit=d37c16111dbe38ea29194f20ac9de03cff8dfc1c
            git init -q "$task_build/xdotool-source"
            git -C "$task_build/xdotool-source" remote add origin https://github.com/jordansissel/xdotool.git
            git -C "$task_build/xdotool-source" fetch --depth 1 origin "$task_xdotool_commit"
            git -C "$task_build/xdotool-source" checkout --detach FETCH_HEAD
            [ "$(git -C "$task_build/xdotool-source" rev-parse HEAD)" = "$task_xdotool_commit" ]
            git -C "$task_build/xdotool-source" archive --format=tar --prefix=xdotool-4.20260303.1/ \
                --output="$task_build/SOURCES/xdotool-4.20260303.1.tar" "$task_xdotool_commit"
            gzip -n "$task_build/SOURCES/xdotool-4.20260303.1.tar"
            cp "$task_root/packaging/rpm/rhel/xdotool.spec" "$task_build/SPECS/"
            rpmbuild --define "_topdir $task_build" -ba "$task_build/SPECS/xdotool.spec"
        fi
        rpmbuild --define "_topdir $task_build" -ba "$task_build/SPECS/jarvis-assistant.spec"
        find "$task_build/RPMS" "$task_build/SRPMS" -name '*.rpm' -type f -exec cp '{}' "$task_output/" \;
        ;;
    arch)
        command -v makepkg >/dev/null
        . /etc/os-release
        [ "$ID" = 'arch' ] || { echo 'Alvo arch exige ambiente Arch.' >&2; exit 2; }
        task_build=$(mktemp -d "$task_output/.arch-build-XXXXXX")
        cp "$task_root/packaging/arch/PKGBUILD" "$task_build/PKGBUILD"
        export JARVIS_SOURCE_ROOT=$task_root
        export PKGDEST=$task_output
        cd "$task_build"
        makepkg --nodeps --force
        ;;
    *) echo "Alvo ainda nao implementado: $task_target" >&2; exit 2 ;;
esac
