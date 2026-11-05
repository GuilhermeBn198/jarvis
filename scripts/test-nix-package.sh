#!/bin/sh
# Install and exercise a Nix profile transition in a disposable profile.
set -eu
task_store=${1:?usage: test-nix-package.sh STORE-OUTPUT [--gui] [PREVIOUS-STORE-OUTPUT]}
task_gui=${2:-}
task_previous_store=${3:-${JARVIS_NIX_PREVIOUS_STORE:-}}
case "$task_gui" in ''|--gui) ;; *) echo 'usage: test-nix-package.sh STORE-OUTPUT [--gui] [PREVIOUS-STORE-OUTPUT]' >&2; exit 2 ;; esac
task_checks=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
task_root=$(CDPATH= cd -P "$task_checks/.." && pwd)
command -v nix >/dev/null || { echo 'Nix package manager is required.' >&2; exit 2; }
task_nix_profile() {
    task_nix_action=$1
    shift
    if [ -n "${JARVIS_SOURCE_TREE:-}" ]; then
        nix --extra-experimental-features 'nix-command flakes' profile "$task_nix_action" --impure "$@"
    else
        nix --extra-experimental-features 'nix-command flakes' profile "$task_nix_action" "$@"
    fi
}
task_store=$(readlink -f "$task_store")
[ -x "$task_store/bin/jarvis" ] || { echo 'Nix output has no jarvis launcher.' >&2; exit 2; }
if [ -n "$task_previous_store" ]; then
    task_previous_store=$(readlink -f "$task_previous_store")
    [ -x "$task_previous_store/bin/jarvis" ] || {
        echo 'Previous Nix output has no jarvis launcher.' >&2
        exit 2
    }
    [ "$task_previous_store" != "$task_store" ] || {
        echo 'Previous and current Nix outputs are identical.' >&2
        exit 2
    }
    export JARVIS_SOURCE_TREE=${JARVIS_SOURCE_TREE:-$task_root}
fi
case "$(uname -m)" in
    x86_64) task_system=x86_64-linux ;;
    *) echo 'Nix profile smoke suporta somente x86_64.' >&2; exit 2 ;;
esac
task_flake="$task_root#packages.$task_system.jarvis-assistant"
task_xdg_store=$(nix-store -qR "$task_store" | grep -- '-xdg-utils-' | head -n 1)
[ -n "$task_xdg_store" ] || { echo 'Nix output has no xdg-utils runtime dependency.' >&2; exit 2; }
grep -F "$task_xdg_store/bin" "$task_store/bin/jarvis" >/dev/null
test -x "$task_xdg_store/bin/xdg-open"
grep -F 'Copyright (c) 2025 opencode' "$task_store/share/licenses/jarvis/opencode-MIT.txt" >/dev/null
grep -F 'Permission is hereby granted' "$task_store/share/licenses/jarvis/opencode-MIT.txt" >/dev/null
[ -x "$task_store/lib/jarvis/runtime/bin/python3" ] || {
    echo 'Nix output has no bound Python runtime.' >&2
    exit 2
}
task_tmp=$(mktemp -d)
trap 'rm -rf "$task_tmp"' EXIT HUP INT TERM
task_profile=$task_tmp/profile
task_data=$task_tmp/data
task_profile_flake=$task_flake
task_profile_store=$task_store
if [ -n "$task_previous_store" ]; then
    task_upgrade_flake_dir=$task_tmp/upgrade-flake
    mkdir -p "$task_upgrade_flake_dir"
    cp "$task_root/flake.lock" "$task_upgrade_flake_dir/flake.lock"
    task_write_upgrade_flake() {
        task_source_store=$1
        cat > "$task_upgrade_flake_dir/flake.nix" <<EOF
{
  description = "Jarvis package profile transition test";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/714a5f8c4ead6b31148d829288440ed033ccc041";
  outputs = { self, nixpkgs }:
    let pkgs = import nixpkgs { system = "$task_system"; };
    in {
      packages."$task_system".jarvis-assistant = pkgs.symlinkJoin {
        name = "jarvis-assistant";
        paths = [ $task_source_store ];
      };
    };
}
EOF
    }
    task_write_upgrade_flake "$task_previous_store"
    task_profile_flake="path:$task_upgrade_flake_dir#packages.$task_system.jarvis-assistant"
    task_profile_store=$task_previous_store
    export JARVIS_NIX_TEST_FLAKE_URL=$task_profile_flake
fi
export XDG_DATA_HOME=$task_data PYTHONDONTWRITEBYTECODE=1
mkdir -p "$task_data/jarvis"
printf '%s\n' preserved > "$task_data/jarvis/package-test"

task_nix_profile install \
    --profile "$task_profile" "$task_profile_flake"
task_installed_binary=$(readlink -f "$task_profile/bin/jarvis")
case "$task_installed_binary" in
    *"${task_profile_store##*/}"*) ;;
    *) echo 'Installed Nix profile does not point to the expected package output.' >&2; exit 2 ;;
esac
"$task_profile/bin/jarvis" --doctor
test "$("$task_profile_store/lib/jarvis/bin/opencode" --version)" = 1.18.23
"$task_profile_store/lib/jarvis/runtime/bin/python3" - <<'PY'
import importlib
for name in ('faster_whisper', 'piper', 'mcp', 'httpx', 'dbus_next'):
    importlib.import_module(name)
print('Nix Python runtime imports passed')
PY
test "$(cat "$task_data/jarvis/package-test")" = preserved

if [ -n "$task_previous_store" ]; then
    task_write_upgrade_flake "$task_store"
    task_nix_profile upgrade --profile "$task_profile" --all
    task_profile_binary=$(readlink -f "$task_profile/bin/jarvis")
    case "$task_profile_binary" in
        *"${task_store##*/}"*) ;;
        *) echo 'Nix profile upgrade did not select the current package output.' >&2; exit 2 ;;
    esac
    "$task_profile/bin/jarvis" --doctor
    test "$(cat "$task_data/jarvis/package-test")" = preserved
else
    printf '%s\n' 'SKIP: true Nix profile upgrade requires a previous store output.'
fi

"$task_store/lib/jarvis/runtime/bin/python3" - <<'PY'
import importlib
for name in ('faster_whisper', 'piper', 'mcp', 'httpx', 'dbus_next', 'libei'):
    importlib.import_module(name)
print('Current Nix Python runtime imports passed')
PY

if [ "$task_gui" = --gui ]; then
    [ -x "$task_store/bin/jarvis-overlay" ] || {
        echo 'Nix output has no jarvis-overlay launcher.' >&2
        exit 2
    }
    python3 "$task_checks/test-overlay-instance.py" "$task_store/bin/jarvis-overlay"
fi

nix --extra-experimental-features 'nix-command flakes' profile remove \
    --profile "$task_profile" --all
test ! -e "$task_profile/bin/jarvis"
test "$(cat "$task_data/jarvis/package-test")" = preserved
if [ -n "$task_previous_store" ]; then
    printf '%s\n' 'PASS: Nix profile old-to-current upgrade, runtime imports, removal and user data preservation'
else
    printf '%s\n' 'PASS: Nix profile install, runtime imports, removal and user data preservation'
fi
