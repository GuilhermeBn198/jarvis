ARG JARVIS_VOID_LIBC=glibc
FROM ghcr.io/void-linux/void-${JARVIS_VOID_LIBC}-full:latest AS bootstrap
ARG JARVIS_VOID_REPOSITORY_BASE=https://repo-default.voidlinux.org/current
RUN xbps-install -Syu xbps && xbps-install -Syu
# base-chroot intentionally replaces normal shell/grep/util-linux packages.
# Install into an empty root, as required by upstream's ethereal build mode.
COPY packaging/void/repository-url.sh /usr/local/bin/jarvis-void-repository-url
RUN mkdir -p /var/cache/xbps /rootfs/var/db/xbps /rootfs/var/cache/xbps /rootfs/etc/xbps.d && \
    cp -a /var/db/xbps/keys /rootfs/var/db/xbps/ && \
    cp -a /var/cache/xbps/. /rootfs/var/cache/xbps/ && \
    task_arch=$(xbps-uhelper arch) && \
    task_repo=$(jarvis-void-repository-url "$task_arch" main) && \
    task_bootstrap=$(jarvis-void-repository-url "$task_arch" bootstrap) && \
    printf 'repository=%s\nrepository=%s\n' "$task_bootstrap" "$task_repo" > /rootfs/etc/xbps.d/00-repositories.conf && \
    XBPS_ARCH="$task_arch" xbps-install -r /rootfs -c /var/cache/xbps -Sy \
    -R "$task_repo" \
    -R "$task_bootstrap" \
    base-chroot git rust cargo nodejs python3 python3-devel \
    python3-pip pkg-config gtk+3-devel libwebkit2gtk41-devel libffi-devel ca-certificates mesa tar zstd && \
    rm -rf /rootfs/var/cache/xbps
FROM scratch
ARG JARVIS_VOID_TARGET=void-glibc
ARG JARVIS_VOID_PACKAGES_COMMIT=08c37783199592347f91cc3e3bf6f97213450ec5
COPY --from=bootstrap /rootfs /
WORKDIR /build/jarvis
# The upstream ethereal mode is restricted to this disposable build image.
# It deliberately uses the container root as its native build environment.
RUN git init -q /build/void-packages && \
    git -C /build/void-packages remote add origin https://github.com/void-linux/void-packages.git && \
    git -C /build/void-packages fetch --depth 1 origin "$JARVIS_VOID_PACKAGES_COMMIT" && \
    git -C /build/void-packages checkout --detach FETCH_HEAD && \
    ln -s / /build/void-packages/masterdir && \
    xbps-uhelper arch > /.xbps_chroot_init
ENV XBPS_CHROOT_CMD=ethereal \
    XBPS_ALLOW_CHROOT_BREAKOUT=yes \
    JARVIS_VOID_PACKAGES=/build/void-packages \
    JARVIS_VOID_PACKAGES_COMMIT=$JARVIS_VOID_PACKAGES_COMMIT
COPY . .
ENV CARGO_HTTP_TIMEOUT=600 CARGO_NET_RETRY=10
RUN git init -q && git add -A && \
    sh scripts/build-package.sh --target "$JARVIS_VOID_TARGET" --output /out
CMD ["sh", "-c", "set -eu; task_package=$(find /out -maxdepth 1 -type f -name '*.xbps' -print -quit); test -n \"$task_package\"; python3 scripts/repack-xbps-previous.py \"$task_package\" --output-dir /out/upgrade; task_previous=$(find /out/upgrade -maxdepth 1 -type f -name '*.xbps' -print -quit); test -n \"$task_previous\"; cp \"$task_package\" /export/; cp \"$task_previous\" /export-upgrade/"]
