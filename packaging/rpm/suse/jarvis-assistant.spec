# Experimental openSUSE Tumbleweed package; not an official repository submission.
%global debug_package %{nil}
%global __strip /bin/true
%global __requires_exclude ^python3dist[(].*
%global __provides_exclude ^python3.*dist[(].*
%global __requires_exclude_from ^/usr/lib/jarvis/(python|[.]opencode/node_modules)/.*
%global __provides_exclude_from ^/usr/lib/jarvis/(python|[.]opencode/node_modules)/.*

Name:           jarvis-assistant
Version:        0.1.0
Release:        1
Summary:        Assistente pessoal por voz com overlay Linux
License:        Apache-2.0 AND MIT AND GPL-3.0-or-later
URL:            https://github.com/GuilhermeBn198/jarvis
Source0:        jarvis-%{version}.tar.gz
ExclusiveArch:  x86_64 aarch64
BuildRequires:  rust cargo gcc gcc-c++ make pkgconf-pkg-config
BuildRequires:  gtk3-devel webkitgtk3-devel
BuildRequires:  python3 python3-pip python-rpm-macros
BuildRequires:  nodejs npm
Requires:       python(abi) = %{python3_version}
Requires:       libgtk-3-0 libwebkit2gtk-4_1-0 ffmpeg libpulse0 pulseaudio-utils libX11-6
Requires:       python3-gobject gobject-introspection typelib-1_0-Atspi-2_0 at-spi2-core
Requires:       alsa-utils xdotool wl-clipboard xclip libstdc++6 libgcc_s1 libgomp1

%description
Assistente por voz com overlay, agente e runtime Python privado compilado
para o ABI do alvo. Configuracao, autenticacao e modelos pertencem ao usuario.
Nao executa pip ou downloads durante a instalacao do RPM.

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
* Thu Oct 15 2026 Jarvis contributors - 0.1.0-1
- Initial local Tumbleweed recipe; package and desktop validation pending.
