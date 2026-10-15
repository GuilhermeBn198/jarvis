FROM rust:1.95-slim-trixie
RUN apt-get update && apt-get install -y --no-install-recommends \
    debhelper dpkg-dev pkg-config libgtk-3-dev libwebkit2gtk-4.1-dev \
    python3 python3-pip python3-venv python3-gi gir1.2-atspi-2.0 nodejs npm \
    ca-certificates xz-utils && rm -rf /var/lib/apt/lists/*
WORKDIR /build/jarvis
COPY . .
RUN cp -a packaging/debian debian && dpkg-buildpackage -us -uc -b -d
CMD ["sh", "-c", "cp /build/*.deb /out/"]
