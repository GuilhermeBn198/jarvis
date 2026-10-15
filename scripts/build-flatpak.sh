#!/bin/sh
# Resolve network dependencies first, then build within Flatpak's offline sandbox.
set -eu
task_root=$(CDPATH= cd -P "$(dirname "$0")/.." && pwd)
task_output=${1:-$task_root/dist/flatpak}
mkdir -p "$task_output"
task_output=$(CDPATH= cd -P "$task_output" && pwd)
[ "$(uname -m)" = x86_64 ] || { echo 'Pins ARM64 ainda aguardam validacao; nao use os commits x86_64.' >&2; exit 2; }
task_require_commit() {
    task_actual=$(flatpak info --user --show-commit "$1")
    [ "$task_actual" = "$2" ] || { echo "Commit instalado de $1 difere do build fixado: $task_actual" >&2; exit 2; }
}
task_require_commit org.gnome.Sdk//49 faf37bdc962236ef8e61fd0b289fd311f7961cc5a7b4bc11a6e29506d7874003
task_require_commit org.gnome.Platform//49 2bb946ea4ebb050f6a32f90e979feb975b08280d1ff1aac881dec3d1361ad84d
task_require_commit org.freedesktop.Sdk.Extension.rust-stable//25.08 09784a9989ae5a7fda6a2280033ca9aa32aac6907961da8b18be4590dd261507
if [ ! -f "$task_output/sources/com.jarvis.overlay.json" ]; then
    python3 "$task_root/scripts/prepare-flatpak.py" --output "$task_output/sources"
fi
python3 "$task_root/scripts/prepare-flatpak.py" --manifest-only "$task_output/sources/jarvis-sources.tar.gz" --output "$task_output/sources"
flatpak run org.flatpak.Builder --user --force-clean --repo="$task_output/repo" \
    --state-dir="$task_output/state" "$task_output/build" "$task_output/sources/com.jarvis.overlay.json"
task_agent_version=$(flatpak build "$task_output/build" /app/lib/jarvis/bin/opencode --version)
[ "$task_agent_version" = '1.18.23' ] || { echo "Agente foi alterado pelo empacotamento: $task_agent_version" >&2; exit 2; }
flatpak build-bundle --runtime-repo=https://flathub.org/repo/flathub.flatpakrepo \
    "$task_output/repo" "$task_output/jarvis-x86_64.flatpak" com.jarvis.overlay stable
sha256sum "$task_output/jarvis-x86_64.flatpak" > "$task_output/jarvis-x86_64.flatpak.sha256"
