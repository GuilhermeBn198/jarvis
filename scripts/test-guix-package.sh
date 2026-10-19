#!/bin/sh
# Install a built Guix output into a disposable profile and verify removal.
set -eu
task_store=${1:?usage: test-guix-package.sh STORE-OUTPUT}
command -v guix >/dev/null || { echo 'GNU Guix is required.' >&2; exit 2; }
task_store=$(readlink -f "$task_store")
[ -x "$task_store/bin/jarvis" ] || { echo 'Guix output has no jarvis launcher.' >&2; exit 2; }
task_tmp=$(mktemp -d)
trap 'rm -rf "$task_tmp"' EXIT HUP INT TERM
task_profile=$task_tmp/profile
task_data=$task_tmp/data
export XDG_DATA_HOME=$task_data PYTHONDONTWRITEBYTECODE=1
mkdir -p "$task_data/jarvis"
printf '%s\n' preserved > "$task_data/jarvis/package-test"

guix package --profile="$task_profile" --install "$task_store"
. "$task_profile/etc/profile"
"$task_profile/bin/jarvis" --doctor
test "$("$task_store/lib/jarvis/bin/opencode" --version)" = 1.18.23
task_pythonpath=$(sed -n 's/^export PYTHONPATH="\([^$]*\).*/\1/p' "$task_store/bin/jarvis")
[ -n "$task_pythonpath" ] || { echo 'Guix launcher has no embedded Python module path.' >&2; exit 1; }
PYTHONPATH="$task_pythonpath${PYTHONPATH:+:$PYTHONPATH}" \
"$task_store/lib/jarvis/runtime/bin/python3" - <<'PY'
import importlib
for name in ('faster_whisper', 'piper', 'mcp', 'httpx', 'dbus_next'):
    importlib.import_module(name)
print('Guix Python runtime imports passed')
PY
test "$(cat "$task_data/jarvis/package-test")" = preserved

guix package --profile="$task_profile" --remove jarvis-assistant
test ! -e "$task_profile/bin/jarvis"
test "$(cat "$task_data/jarvis/package-test")" = preserved
printf '%s\n' 'PASS: Guix profile install, runtime imports, removal and user data preservation'
