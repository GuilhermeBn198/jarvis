FROM opensuse/tumbleweed:latest
RUN zypper --non-interactive refresh --force && \
    zypper --non-interactive dup --no-recommends && \
    zypper --non-interactive install --no-recommends \
    rpm-build python-rpm-macros rust cargo gcc gcc-c++ make pkgconf-pkg-config \
    gtk3-devel webkitgtk3-devel python3 python3-pip python3-gobject \
    typelib-1_0-Atspi-2_0 nodejs npm ca-certificates git tar gzip && \
    zypper clean --all
WORKDIR /build/jarvis
COPY . .
ARG JARVIS_TEST_PACKAGE_UPGRADE=0
# The source archiver inventories Git files; Docker intentionally omits .git.
# A local empty index preserves its allowlist and ignore rules for this context.
RUN git init --quiet && \
    if [ "$JARVIS_TEST_PACKAGE_UPGRADE" = 1 ]; then \
        JARVIS_TEST_PACKAGE_UPGRADE=1 scripts/build-package.sh --target suse --output /dist; \
    else \
        scripts/build-package.sh --target suse --output /dist; \
    fi
CMD ["sh", "-c", "cp /dist/*.rpm /out/"]
