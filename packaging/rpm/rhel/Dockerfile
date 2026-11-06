FROM almalinux:10
COPY scripts/dnf-install-with-metadata-retry.sh /usr/local/bin/dnf-install-with-metadata-retry
RUN dnf install -y dnf-plugins-core epel-release && \
    dnf config-manager --set-enabled crb && \
    /usr/local/bin/dnf-install-with-metadata-retry install -y --setopt=install_weak_deps=False \
    rpm-build rust cargo gcc gcc-c++ make pkgconf-pkg-config \
    gtk3-devel webkit2gtk4.1-devel python3 python3-pip python3-rpm-macros \
    nodejs npm git ca-certificates tar gzip \
    libX11-devel libXtst-devel libXinerama-devel libxkbcommon-devel 'perl(Pod::Man)' && \
    dnf clean all
WORKDIR /build/jarvis
COPY . .
ARG JARVIS_TEST_PACKAGE_UPGRADE=0
RUN git init --quiet && \
    if [ "$JARVIS_TEST_PACKAGE_UPGRADE" = 1 ]; then \
        JARVIS_TEST_PACKAGE_UPGRADE=1 scripts/build-package.sh --target rhel --output /dist; \
    else \
        scripts/build-package.sh --target rhel --output /dist; \
    fi
CMD ["sh", "-c", "cp /dist/*.rpm /out/"]
