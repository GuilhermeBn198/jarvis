# Local bundled release package, not an official Fedora repository submission.
%global debug_package %{nil}
%global __strip /bin/true
# Vendored wheels are private application dependencies, not system providers.
%global __requires_exclude ^python3dist[(].*
%global __provides_exclude ^python3.*dist[(].*
%global __requires_exclude_from ^/usr/lib/jarvis/(python|[.]opencode/node_modules)/.*
%global __provides_exclude_from ^/usr/lib/jarvis/(python|[.]opencode/node_modules)/.*

Name:           jarvis-assistant
Version:        0.1.0
Release:        1%{?dist}
Summary:        Assistente pessoal por voz com overlay Linux
License:        Apache-2.0 AND MIT AND GPL-3.0-or-later
URL:            https://github.com/GuilhermeBn198/jarvis
Source0:        jarvis-%{version}.tar.gz
ExclusiveArch:  x86_64 aarch64
BuildRequires:  rust cargo gcc gcc-c++ make pkgconf-pkg-config
BuildRequires:  gtk3-devel webkit2gtk4.1-devel
BuildRequires:  python3 python3-pip python3-rpm-macros
BuildRequires:  nodejs npm
Requires:       python(abi) = %{python3_version}
Requires:       gtk3 webkit2gtk4.1 ffmpeg-free pulseaudio-libs pulseaudio-utils libX11
Requires:       python3-gobject gobject-introspection at-spi2-core alsa-utils xdotool wl-clipboard xclip
Requires:       libstdc++ libgcc libgomp

%description
Assistente por voz, captura autorizada e controle do desktop. Inclui overlay,
agente e runtime Python privado. Modelos e autenticacao sao configurados
pelo usuario. Nao executa pip ou downloads durante a instalacao do RPM.

%prep
%setup -q -n jarvis-%{version}

%build
cargo build --release --locked --manifest-path gui/src-tauri/Cargo.toml
npm ci --prefix .opencode --ignore-scripts
python3 scripts/fetch-opencode.py --target %{_arch}-glibc --output opencode-package

%install
python3 scripts/prepare-package.py --prefix /usr --destdir %{buildroot} \
    --overlay gui/src-tauri/target/release/jarvis-overlay \
    --python /usr/bin/python3 --opencode opencode-package

%files
/usr/bin/jarvis
/usr/bin/jarvis-overlay
/usr/lib/jarvis
/usr/share/applications/com.jarvis.overlay.desktop
/usr/share/icons/hicolor/128x128/apps/jarvis.png
%doc /usr/share/doc/jarvis
%license /usr/share/licenses/jarvis

%changelog
* Wed Oct 14 2026 Jarvis contributors - 0.1.0-1
- Initial local Fedora package recipe; runtime matrix validation pending.
