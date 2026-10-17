# Local bundled source recipe; not an official Gentoo repository submission.
EAPI=8
inherit xdg
DESCRIPTION="Voice assistant with native Linux overlay"
HOMEPAGE="https://github.com/GuilhermeBn198/jarvis"
LICENSE="Apache-2.0 MIT GPL-3"
SLOT="0"
KEYWORDS="~amd64 ~arm64"
# Cargo/npm/pip resolve private dependencies at build time only. Preserve Bun's
# appended executable payload; Portage must not strip the private executables.
RESTRICT="network-sandbox strip"
S="${WORKDIR}/jarvis-${PV}"
RDEPEND="
 dev-lang/python:3.14
 dev-python/pygobject:3[python_targets_python3_14]
 x11-libs/gtk+:3[introspection,X,wayland]
 net-libs/webkit-gtk:4.1[introspection,X,wayland]
 app-accessibility/at-spi2-core[introspection]
 media-video/ffmpeg[alsa,pulseaudio,sdl]
 media-libs/libpulse
 media-sound/alsa-utils
 x11-misc/xdotool
 gui-apps/wl-clipboard
 x11-misc/xclip"
DEPEND="${RDEPEND}"
BDEPEND="dev-lang/rust-bin dev-vcs/git net-libs/nodejs[npm]
 dev-python/pip[python_targets_python3_14] virtual/pkgconfig"

src_unpack() {
    # The driver creates a sanitized source archive; Manifest records its hash.
    tar -xzf "${FILESDIR}/jarvis-${PV}.tar.gz" -C "${WORKDIR}" || die
}

src_compile() {
    local task_arch
    case ${ARCH} in amd64) task_arch=x86_64 ;; arm64) task_arch=aarch64 ;; *) die "Unsupported native architecture" ;; esac
    cargo build --release --locked --jobs 2 --manifest-path gui/src-tauri/Cargo.toml || die
    npm ci --prefix .opencode --ignore-scripts || die
    python3.14 scripts/fetch-opencode.py --target "${task_arch}-glibc" --output opencode-package || die
}

src_install() {
    python3.14 scripts/prepare-package.py --prefix /usr --destdir "${D}" \
        --overlay gui/src-tauri/target/release/jarvis-overlay \
        --python /usr/bin/python3.14 --opencode opencode-package || die
    if [[ -d "${D}/usr/share/doc/jarvis" ]]; then
        rm -rf "${D}/usr/share/doc/jarvis" || die
        # The installed-file manifest tracks this documentation path too.
        # Keep it uncompressed so Portage's post-merge file list still agrees.
        docompress -x "/usr/share/doc/${PF}"
        dodoc "${S}/docs/linux.md"
    fi
    find "${D}/usr/lib/jarvis/.opencode/node_modules/@msgpackr-extract" \
        -type f -name '*.musl.node' -delete || die
    python3.14 - "${D}/usr" <<'PY' || die
from pathlib import Path
import json,sys
root=Path(sys.argv[1]);manifest=root/'lib/jarvis/install-manifest.json'
data=json.loads(manifest.read_text())
data['files']=sorted(str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() or p.is_symlink())
manifest.write_text(json.dumps(data,indent=2)+'\n')
PY
}
