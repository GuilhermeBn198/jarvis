FROM ghcr.io/void-linux/void-glibc-full:latest AS bootstrap
RUN xbps-install -Syu xbps && xbps-install -Syu
# base-chroot intentionally replaces normal shell/grep/util-linux packages.
# Install into an empty root, as required by upstream's ethereal build mode.
RUN mkdir -p /rootfs/var/db/xbps /rootfs/var/cache/xbps /rootfs/etc/xbps.d && \
    cp -a /var/db/xbps/keys /rootfs/var/db/xbps/ && \
    cp -a /var/cache/xbps/. /rootfs/var/cache/xbps/ && \
    printf '%s\n' 'repository=https://repo-default.voidlinux.org/current/bootstrap' \
    'repository=https://repo-default.voidlinux.org/current' > /rootfs/etc/xbps.d/00-repositories.conf && \
    xbps-install -r /rootfs -c /var/cache/xbps -Sy \
    -R https://repo-default.voidlinux.org/current \
    -R https://repo-default.voidlinux.org/current/bootstrap \
    base-chroot git rust cargo nodejs python3 python3-devel \
    python3-pip pkg-config gtk+3-devel libwebkit2gtk41-devel libffi-devel ca-certificates && \
    rm -rf /rootfs/var/cache/xbps
FROM scratch
COPY --from=bootstrap /rootfs /
WORKDIR /build/jarvis
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
COPY . .
ENV CARGO_HTTP_TIMEOUT=600 CARGO_NET_RETRY=10
RUN git init -q && git add -A && \
    sh scripts/build-package.sh --target void-glibc --output /out
CMD ["sh", "-c", "find /out -name '*.xbps' -type f -exec cp '{}' /export/ ';'"]
