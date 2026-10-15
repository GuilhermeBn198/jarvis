#!/bin/sh
# Resolve network dependencies first, then build within Flatpak's offline sandbox.
set -eu
task_root=$(CDPATH= cd -P "$(dirname "$0")/.." && pwd)
task_output=${1:-$task_root/dist/flatpak}
mkdir -p "$task_output"
task_output=$(CDPATH= cd -P "$task_output" && pwd)
task_arch=$(uname -m)
task_pins=$(python3 - "$task_root/packaging/flatpak/runtime-pins.json" "$task_arch" <<'PYCODE'
import json,sys
pins=json.load(open(sys.argv[1])).get(sys.argv[2])
if not pins:sys.exit('Arquitetura Flatpak nao suportada: '+sys.argv[2])
for ref,commit in pins.items():print(ref,commit)
PYCODE
)
task_require_commit() {
    task_actual=$(flatpak info --user --show-commit "$1")
    [ "$task_actual" = "$2" ] || { echo "Commit instalado de $1 difere do build fixado: $task_actual" >&2; exit 2; }
}
printf '%s\n' "$task_pins" | while read -r task_ref task_commit; do
    task_require_commit "$task_ref" "$task_commit"
done
if [ ! -f "$task_output/sources/com.jarvis.overlay.json" ]; then
    python3 "$task_root/scripts/prepare-flatpak.py" --output "$task_output/sources"
fi
python3 "$task_root/scripts/prepare-flatpak.py" --manifest-only "$task_output/sources/jarvis-sources.tar.gz" --output "$task_output/sources"
flatpak run org.flatpak.Builder --user --force-clean --repo="$task_output/repo" \
    --state-dir="$task_output/state" "$task_output/build" "$task_output/sources/com.jarvis.overlay.json"
task_agent_version=$(flatpak build "$task_output/build" /app/lib/jarvis/bin/opencode --version)
[ "$task_agent_version" = '1.18.23' ] || { echo "Agente foi alterado pelo empacotamento: $task_agent_version" >&2; exit 2; }
flatpak build-bundle --runtime-repo=https://flathub.org/repo/flathub.flatpakrepo \
    "$task_output/repo" "$task_output/jarvis-$task_arch.flatpak" com.jarvis.overlay stable
sha256sum "$task_output/jarvis-$task_arch.flatpak" > "$task_output/jarvis-$task_arch.flatpak.sha256"
