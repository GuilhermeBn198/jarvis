FROM registry.fedoraproject.org/fedora:44
RUN dnf install -y --setopt=install_weak_deps=False \
    rpm-build rust cargo gcc gcc-c++ make pkgconf-pkg-config \
    gtk3-devel webkit2gtk4.1-devel python3 python3-pip python3-rpm-macros \
    nodejs npm git ca-certificates && dnf clean all
WORKDIR /build/jarvis
COPY . .
ARG JARVIS_TEST_PACKAGE_UPGRADE=0
RUN git init -q && \
    if [ "$JARVIS_TEST_PACKAGE_UPGRADE" = 1 ]; then \
        JARVIS_TEST_PACKAGE_UPGRADE=1 scripts/build-package.sh --target fedora --output /dist; \
    else \
        scripts/build-package.sh --target fedora --output /dist; \
    fi
CMD ["sh", "-c", "cp /dist/*.rpm /out/"]
