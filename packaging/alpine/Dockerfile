FROM alpine:3.24
RUN apk add --no-cache abuild build-base cmake ninja git python3 python3-dev \
    py3-pip py3-pybind11-dev py3-numpy py3-onnxruntime linux-headers \
    openblas-dev ffmpeg-dev pkgconf rust cargo nodejs npm gtk+3.0-dev \
    webkit2gtk-4.1-dev patchelf ca-certificates
# abuild's restricted dependency installer needs a populated index cache.
RUN apk add --no-cache ffmpeg ffplay pulseaudio-utils xdotool wl-clipboard \
    xclip py3-gobject3 alsa-utils && apk update
WORKDIR /build/jarvis
COPY . .
RUN adduser -D -G abuild builder && mkdir -p /out && \
    chown -R builder:abuild /build/jarvis /out
USER builder
RUN abuild-keygen -a -n
USER root
# Trust only this disposable builder's public key for its local index.
RUN cp /home/builder/.abuild/*.pub /etc/apk/keys/
USER builder
# The Docker context is already filtered. Inventory it for source-archive.py.
RUN git init -q && git add -A && \
    sh scripts/build-package.sh --target alpine --output /out
# Export into bind mounts whose host UID may differ from the abuild user.
USER root
CMD ["sh", "-c", "find /out -name '*.apk' -type f -exec cp '{}' /export/ ';'; cp /home/builder/.abuild/*.pub /export/"]
