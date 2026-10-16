#!/bin/sh
# Build native musl dependencies; run only inside the target Alpine environment.
set -eu
task_source=${1:?source root}
task_native=${2:?native build directory}
mkdir -p "$task_native/wheels"
task_native=$(CDPATH= cd -P "$task_native" && pwd)
task_fetch() {
    git init -q "$3"
    git -C "$3" remote add origin "$1"
    git -C "$3" fetch --depth 1 origin "$2"
    git -C "$3" checkout --detach FETCH_HEAD
    test "$(git -C "$3" rev-parse HEAD)" = "$2"
}
task_fetch https://github.com/OpenNMT/CTranslate2.git 8d91aa08225004755360daa43deb62b35b1ed65d "$task_native/ct2-source"
git -C "$task_native/ct2-source" submodule update --init --recursive --depth 1
task_fetch https://github.com/OHF-Voice/piper1-gpl.git 639388b6317fc4731e91d53da42aea68fd4166ff "$task_native/piper-source"
task_fetch https://github.com/espeak-ng/espeak-ng.git 724808c5a83f9ef95fdd0db886ba7ba537ff224a "$task_native/espeak-source"
python3 "$task_source/packaging/alpine/patch-sources.py" "$task_native"
export CMAKE_POLICY_VERSION_MINIMUM=3.5 CMAKE_BUILD_PARALLEL_LEVEL=2
cmake -S "$task_native/ct2-source" -B "$task_native/ct2-build" -G Ninja \
    -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$task_native/ctranslate2" -DWITH_MKL=OFF \
    -DWITH_OPENBLAS=ON -DWITH_RUY=ON -DOPENMP_RUNTIME=COMP -DBUILD_CLI=OFF
cmake --build "$task_native/ct2-build" --parallel 2
cmake --install "$task_native/ct2-build"
python3 -m venv --system-site-packages "$task_native/build-python"
"$task_native/build-python/bin/pip" install setuptools wheel pybind11 scikit-build pathvalidate
CTRANSLATE2_ROOT="$task_native/ctranslate2" "$task_native/build-python/bin/pip" wheel \
    --no-build-isolation --no-deps --wheel-dir "$task_native/wheels" "$task_native/ct2-source/python"
"$task_native/build-python/bin/pip" wheel --no-build-isolation --no-deps \
    --wheel-dir "$task_native/wheels" "$task_native/piper-source"
python3 -m venv --without-pip --system-site-packages "$task_native/runtime"
"$task_native/build-python/bin/pip" --python "$task_native/runtime/bin/python" install \
    --report "$task_native/python-report.json" --find-links "$task_native/wheels" \
    "$task_native"/wheels/ctranslate2-*.whl "$task_native"/wheels/piper_tts-*.whl \
    -r "$task_source/voice/requirements-linux.txt" \
    -r "$task_source/mcp_servers/win_context/requirements.txt" \
    -r "$task_source/mcp_servers/delegate_local/requirements.txt"
"$task_native/build-python/bin/pip" --python "$task_native/runtime/bin/python" check
