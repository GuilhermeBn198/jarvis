ARG ARCH_BASE_IMAGE=archlinux:base
FROM ${ARCH_BASE_IMAGE}
RUN pacman -Syu --noconfirm --needed base-devel rust cargo pkgconf \
    gtk3 webkit2gtk-4.1 python python-pip nodejs npm && \
    useradd -m builder && mkdir -p /build && chown builder:builder /build
WORKDIR /build/jarvis
COPY --chown=builder:builder . .
USER builder
RUN scripts/build-package.sh --target arch --arch "$(uname -m)" --output /build/packages
USER root
CMD ["sh", "-c", "cp /build/packages/*.pkg.tar.* /out/"]
