FROM almalinux:10
RUN dnf install -y dnf-plugins-core epel-release && \
    dnf config-manager --set-enabled crb && \
    dnf install -y --setopt=install_weak_deps=False \
    rpm-build rust cargo gcc gcc-c++ make pkgconf-pkg-config \
    gtk3-devel webkit2gtk4.1-devel python3 python3-pip python3-rpm-macros \
    nodejs npm git ca-certificates tar gzip \
    libX11-devel libXtst-devel libXinerama-devel libxkbcommon-devel 'perl(Pod::Man)' && \
    dnf clean all
WORKDIR /build/jarvis
COPY . .
RUN git init --quiet && scripts/build-package.sh --target rhel --output /dist
CMD ["sh", "-c", "cp /dist/*.rpm /out/"]
