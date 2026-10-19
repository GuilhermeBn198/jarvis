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
    gentoo)
        . /etc/os-release
        [ "$ID" = gentoo ] || { echo 'Alvo gentoo exige ambiente Gentoo.' >&2; exit 2; }
        command -v ebuild >/dev/null
        command -v git >/dev/null
        task_build=$(mktemp -d)
        chmod 0755 "$task_build"
        task_overlay=$task_build/overlay
        task_package=$task_overlay/app-misc/jarvis-assistant
        mkdir -p "$task_package/files" "$task_overlay/profiles" "$task_overlay/metadata" "$task_build/tmp" "$task_build/binpkgs"
        printf '%s\n' jarvis-local > "$task_overlay/profiles/repo_name"
        printf '%s\n' 'masters = gentoo' 'thin-manifests = false' > "$task_overlay/metadata/layout.conf"
        python3 "$task_root/scripts/source-archive.py" --output "$task_package/files/jarvis-0.1.0.tar.gz"
        cp "$task_root/packaging/gentoo/jarvis-assistant-0.1.0.ebuild" "$task_package/"
        export PORTDIR_OVERLAY="${PORTDIR_OVERLAY:+$PORTDIR_OVERLAY }$task_overlay"
        export PORTAGE_TMPDIR=$task_build/tmp PKGDIR=$task_build/binpkgs BINPKG_FORMAT=gpkg
        ebuild "$task_package/jarvis-assistant-0.1.0.ebuild" manifest clean package
        find "$task_build/binpkgs" -type f -name '*.gpkg.tar' -exec cp '{}' "$task_output/" \;
        ;;
    nix)
        command -v nix >/dev/null || { echo 'Alvo nix requer o Nix package manager.' >&2; exit 2; }
        nix --extra-experimental-features 'nix-command flakes' build \
            "$task_root#jarvis-assistant" --out-link "$task_output/jarvis-assistant"
        ;;
    guix)
        command -v guix >/dev/null || { echo 'Alvo guix requer o GNU Guix.' >&2; exit 2; }
        case "$task_arch" in x86_64) ;; *) echo 'Alvo guix atualmente suporta apenas x86_64.' >&2; exit 2 ;; esac
        task_build=$(mktemp -d "$task_output/.guix-build-XXXXXX")
        python3 "$task_root/scripts/prepare-guix-source.py" \
            --output "$task_build/jarvis-guix-source.tar.gz"
        python3 "$task_root/scripts/fetch-opencode.py" \
            --target "$task_arch-glibc" --output "$task_build/opencode-package"
        cp "$task_root/packaging/guix/jarvis.scm" \
            "$task_root/packaging/guix/cargo-crate-sources.scm" "$task_build/"
        (cd "$task_build" && guix build -f ./jarvis.scm \
            --out-link "$task_output/jarvis-assistant")
        ;;
    void-musl)
        . /etc/os-release
        [ "$ID" = void ] || { echo 'Alvo void-musl exige ambiente Void Linux.' >&2; exit 2; }
        command -v bash >/dev/null || { echo 'Alvo void-musl requer bash para executar xbps-src.' >&2; exit 2; }
        [ "$(xbps-uhelper arch)" = "$task_arch-musl" ] || { echo 'Alvo void-musl exige libc musl nativa.' >&2; exit 2; }
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
        python3 - "$task_root/packaging/void-musl/template" "$task_template" <<'PY'
from pathlib import Path
import hashlib,sys
source=Path(sys.argv[1]);target=Path(sys.argv[2])
with (target/'files/jarvis-0.1.0.tar.gz').open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
(target/'template').write_text(source.read_text().replace('@JARVIS_SOURCE_SHA256@',digest))
PY
        (cd "$task_collection" && ./xbps-src -j2 pkg jarvis-assistant)
        find "$task_collection/hostdir/binpkgs" -type f -name "jarvis-assistant-*.$task_arch-musl.xbps" -exec cp '{}' "$task_output/" \;
        ;;
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
        if [ "${JARVIS_TEST_PACKAGE_UPGRADE:-0}" = 1 ]; then
            # Compile once, then create two revisions from the same native build.
            # Keep temporary outputs only until the second packaging pass ends.
            abuild -r -K
            grep -qx 'pkgrel=0' APKBUILD
            sed -i 's/^pkgrel=0$/pkgrel=1/' APKBUILD
            # rootpkg must not reuse control metadata from the first revision.
            rm -rf "$task_build/pkg"
            abuild rootpkg
            abuild clean
        else
            abuild -r
        fi
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
        case "$ID" in
            arch|archarm) ;;
            *) echo 'Alvo arch exige Arch Linux ou Arch Linux ARM.' >&2; exit 2 ;;
        esac
        task_build=$(mktemp -d "$task_output/.arch-build-XXXXXX")
        cp "$task_root/packaging/arch/PKGBUILD" "$task_build/PKGBUILD"
        export JARVIS_SOURCE_ROOT=$task_root
        export PKGDEST=$task_output
        cd "$task_build"
        makepkg --nodeps --force
        ;;
    slackware)
        [ -f /etc/slackware-version ] || { echo 'Alvo slackware exige Slackware Linux.' >&2; exit 2; }
        command -v makepkg >/dev/null || { echo 'Slackware exige a ferramenta makepkg.' >&2; exit 2; }
        task_build=$(mktemp -d "$task_output/.slackware-build-XXXXXX")
        JARVIS_SOURCE_ROOT=$task_root JARVIS_BUILD_ROOT=$task_build \
        JARVIS_PACKAGE_OUTPUT=$task_output ARCH=$task_arch \
            sh "$task_root/packaging/slackware/jarvis.SlackBuild"
        ;;
    solus)
        . /etc/os-release
        [ "$ID" = solus ] || { echo 'Alvo solus exige ambiente Solus.' >&2; exit 2; }
        [ "$task_arch" = x86_64 ] || { echo 'Alvo solus atualmente suporta apenas x86_64.' >&2; exit 2; }
        command -v solbuild >/dev/null || { echo 'Alvo solus requer solbuild.' >&2; exit 2; }
        task_build=$(mktemp -d "$task_output/.solus-build-XXXXXX")
        task_source=$task_build/jarvis-0.1.0.tar.gz
        python3 "$task_root/scripts/source-archive.py" --output "$task_source"
        python3 "$task_root/scripts/prepare-solus-package.py" \
            "$task_root/packaging/solus/package.yml" "$task_source" "$task_build/package.yml"
        (
            cd "$task_build"
            if [ "$(id -u)" -eq 0 ]; then
                solbuild build "$task_build/package.yml"
            else
                command -v sudo >/dev/null || { echo 'Solus package builds require root; install sudo or run this script as root.' >&2; exit 2; }
                sudo solbuild build "$task_build/package.yml"
            fi
        )
        task_artifact=$(find "$task_build" -maxdepth 1 -type f -name 'jarvis-assistant-*.eopkg' -print -quit)
        [ -n "$task_artifact" ] || {
            echo 'solbuild completed without producing an eopkg artifact.' >&2; exit 1;
        }
        cp "$task_artifact" "$task_output/"
        ;;
    *) echo "Alvo ainda nao implementado: $task_target" >&2; exit 2 ;;
esac
