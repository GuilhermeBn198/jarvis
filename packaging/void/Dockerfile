FROM ghcr.io/void-linux/void-glibc-full:latest
RUN xbps-install -Syu xbps && xbps-install -Syu && \
    xbps-install -Sy -R https://repo-default.voidlinux.org/current/bootstrap \
    base-chroot git rust cargo nodejs python3 python3-devel \
    python3-pip pkg-config gtk+3-devel libwebkit2gtk41-devel libffi-devel
WORKDIR /build/jarvis
COPY . .
# The upstream ethereal mode is restricted to this disposable build image.
# It deliberately uses the container root as its native build environment.
RUN git init -q /build/void-packages && \
    git -C /build/void-packages remote add origin https://github.com/void-linux/void-packages.git && \
    git -C /build/void-packages fetch --depth 1 origin dbf843f5f1dad63846b6d147ec10662cf8e8078a && \
    git -C /build/void-packages checkout --detach FETCH_HEAD && \
    ln -s / /build/void-packages/masterdir && \
    xbps-uhelper arch > /.xbps_chroot_init
ENV XBPS_CHROOT_CMD=ethereal \
    XBPS_ALLOW_CHROOT_BREAKOUT=yes \
    JARVIS_VOID_PACKAGES=/build/void-packages
RUN git init -q && git add -A && \
    sh scripts/build-package.sh --target void-glibc --output /out
CMD ["sh", "-c", "find /out -name '*.xbps' -type f -exec cp '{}' /export/ ';'"]
