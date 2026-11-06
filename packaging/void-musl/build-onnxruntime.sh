#!/bin/sh
# Build the CPU-only ONNX Runtime Python wheel for the native musl target.
set -eu
task_native=${1:?native build directory}
task_source=${2:?source checkout root}
task_version=1.24.4
task_sha512=53b3aed02e085c83aa3c7e1faffeae7f70675d6770bc44d148085ded47940f29471eef76e0c4565bbb471f0f814610e0d1892ce9305c63d011fe851a22b1f7ab
task_url=https://github.com/microsoft/onnxruntime/archive/refs/tags/v${task_version}.tar.gz
task_archive=$task_native/onnxruntime-$task_version.tar.gz
task_ort=$task_native/onnxruntime-$task_version
mkdir -p "$task_native/wheels"

if [ ! -f "$task_archive" ]; then
    if [ -n "${JARVIS_ONNX_SOURCE_ARCHIVE:-}" ]; then
        cp "$JARVIS_ONNX_SOURCE_ARCHIVE" "$task_archive"
    else
        python3 - "$task_url" "$task_archive" <<'PY'
from pathlib import Path
import sys,urllib.request
url,destination=sys.argv[1:]
temporary=Path(destination+'.partial')
with urllib.request.urlopen(url,timeout=120) as response, temporary.open('wb') as output:
    while chunk:=response.read(1024*1024):output.write(chunk)
temporary.replace(destination)
PY
    fi
fi
printf '%s  %s\n' "$task_sha512" "$task_archive" | sha512sum -c -

if [ ! -f "$task_ort/.jarvis-musl-patches-applied" ]; then
    rm -rf "$task_ort"
    tar -xzf "$task_archive" -C "$task_native"
    for task_patch in no-execinfo.patch system.patch upb-fix.patch \
        protobuf35-unused-dimension.patch protobuf35-unused-shape.patch \
        protobuf35-check-serialization.patch protobuf35-unused-attr.patch; do
        patch -d "$task_ort" -p1 < "$task_source/packaging/void-musl/patches/$task_patch"
    done
    : > "$task_ort/.jarvis-musl-patches-applied"
fi

export CMAKE_BUILD_PARALLEL_LEVEL=2
python3 "$task_ort/tools/ci_build/build.py" \
    --build_dir "$task_native/onnx-build" \
    --allow_running_as_root --config Release --cmake_generator Ninja \
    --skip_submodule_sync --skip_tests --build_wheel --parallel \
    --cmake_extra_defines CMAKE_BUILD_TYPE=None CMAKE_C_FLAGS=-O2 \
        "CMAKE_CXX_FLAGS=-O2 -Wno-error=maybe-uninitialized -Wno-error=unused-result" \
        Protobuf_USE_STATIC_LIBS=OFF onnxruntime_BUILD_UNIT_TESTS=OFF

task_wheel=$(find "$task_native/onnx-build" "$task_ort" -type f \
    -name "onnxruntime-$task_version-*.whl" -print -quit)
[ -n "$task_wheel" ] && [ -s "$task_wheel" ] || {
    echo "ONNX Runtime $task_version wheel was not produced" >&2
    exit 1
}
cp "$task_wheel" "$task_native/wheels/"
