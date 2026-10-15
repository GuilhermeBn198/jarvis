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
case "$task_target" in
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
