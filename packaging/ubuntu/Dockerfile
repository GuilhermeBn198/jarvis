FROM rust:1.95-slim-trixie AS toolchain
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential debhelper dpkg-dev pkg-config libgtk-3-dev libwebkit2gtk-4.1-dev \
    python3 python3-pip python3-venv python3-gi gir1.2-atspi-2.0 nodejs npm \
    ca-certificates git xz-utils && rm -rf /var/lib/apt/lists/*
# Official Rust toolchains support older glibc; compile the application on Ubuntu.
COPY --from=toolchain /usr/local/rustup /usr/local/rustup
COPY --from=toolchain /usr/local/cargo /usr/local/cargo
ENV RUSTUP_HOME=/usr/local/rustup CARGO_HOME=/usr/local/cargo PATH=/usr/local/cargo/bin:$PATH
WORKDIR /build/jarvis
COPY . .
RUN rustc --version && cp -a packaging/debian debian && dpkg-buildpackage -us -uc -b -d
CMD ["sh", "-c", "cp /build/*.deb /out/"]
