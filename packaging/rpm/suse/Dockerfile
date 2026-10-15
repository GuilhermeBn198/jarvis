FROM opensuse/tumbleweed:latest
RUN zypper --non-interactive install --no-recommends \
    rpm-build python-rpm-macros rust cargo gcc gcc-c++ make pkgconf-pkg-config \
    gtk3-devel webkitgtk3-devel python3 python3-pip python3-gobject \
    typelib-1_0-Atspi-2_0 nodejs npm ca-certificates git tar gzip && \
    zypper clean --all
WORKDIR /build/jarvis
COPY . .
RUN scripts/build-package.sh --target suse --output /dist
CMD ["sh", "-c", "cp /dist/*.rpm /out/"]
