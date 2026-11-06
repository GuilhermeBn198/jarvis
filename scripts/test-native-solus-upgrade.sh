#!/bin/sh
# Upgrade a local Solus package in a disposable Solus container.
set -eu
[ -f /.dockerenv ] || [ -f /run/.containerenv ] || { echo 'Execute apenas em container descartavel.' >&2; exit 2; }
task_old_package=${1:?pacote Solus anterior obrigatorio}
task_new_package=${2:?pacote Solus novo obrigatorio}
task_old_release=${3:?release anterior obrigatorio}
task_new_release=${4:?release novo obrigatorio}
. /etc/os-release
[ "$ID" = solus ] || { echo 'O lifecycle de upgrade exige Solus.' >&2; exit 2; }
[ "$(uname -m)" = x86_64 ] || { echo 'O teste de upgrade Solus exige x86_64.' >&2; exit 2; }
[ -f "$task_old_package" ] && [ -f "$task_new_package" ] || { echo 'Os dois pacotes .eopkg precisam existir.' >&2; exit 2; }
case "$task_old_release:$task_new_release" in
    *[!0-9:]*|:*|*:) echo 'Releases precisam ser inteiros positivos.' >&2; exit 2 ;;
esac
[ "$task_old_release" -gt 0 ] && [ "$task_new_release" -gt "$task_old_release" ] || {
    echo 'A release nova precisa ser maior que a anterior.' >&2
    exit 2
}
command -v eopkg >/dev/null || { echo 'O teste requer eopkg.' >&2; exit 2; }

task_state=$(mktemp -d)
trap 'rm -rf "$task_state" "$task_state.before" "$task_state.after"' EXIT HUP INT TERM
for task_kind in CONFIG DATA CACHE STATE; do
    task_name=$(printf '%s' "$task_kind" | tr '[:upper:]' '[:lower:]')
    mkdir -m 700 "$task_state/$task_name"
    case "$task_kind" in
        CONFIG) XDG_CONFIG_HOME=$task_state/$task_name; export XDG_CONFIG_HOME ;;
        DATA) XDG_DATA_HOME=$task_state/$task_name; export XDG_DATA_HOME ;;
        CACHE) XDG_CACHE_HOME=$task_state/$task_name; export XDG_CACHE_HOME ;;
        STATE) XDG_STATE_HOME=$task_state/$task_name; export XDG_STATE_HOME ;;
    esac
done
export PYTHONDONTWRITEBYTECODE=1

eopkg -y install diffutils
task_old_output=$(eopkg -y install "$task_old_package" 2>&1)
printf '%s\n' "$task_old_output"
printf '%s\n' "$task_old_output" | grep -F "Installing jarvis-assistant, version 0.1.0, release $task_old_release" >/dev/null
command -v jarvis >/dev/null || { echo 'O pacote precisa instalar o launcher jarvis.' >&2; exit 2; }
jarvis --doctor
eopkg check jarvis-assistant

for task_kind in CONFIG DATA CACHE STATE; do
    case "$task_kind" in
        CONFIG) task_dir=$XDG_CONFIG_HOME ;;
        DATA) task_dir=$XDG_DATA_HOME ;;
        CACHE) task_dir=$XDG_CACHE_HOME ;;
        STATE) task_dir=$XDG_STATE_HOME ;;
    esac
    mkdir -p "$task_dir/jarvis"
    printf 'keep-%s\n' "$task_kind" > "$task_dir/jarvis/upgrade-sentinel"
done
find "$task_state" -type f -print0 | sort -z | xargs -0 sha256sum > "$task_state.before"

task_new_output=$(eopkg -y install "$task_new_package" 2>&1)
printf '%s\n' "$task_new_output"
printf '%s\n' "$task_new_output" | grep -F "Installing jarvis-assistant, version 0.1.0, release $task_new_release" >/dev/null
jarvis --doctor
eopkg check jarvis-assistant
find "$task_state" -type f ! -name before ! -name after -print0 | sort -z | xargs -0 sha256sum > "$task_state.after"
cmp "$task_state.before" "$task_state.after" || {
    echo 'Os dados XDG foram alterados durante o upgrade.' >&2
    exit 1
}

eopkg -y remove jarvis-assistant
for task_kind in CONFIG DATA CACHE STATE; do
    case "$task_kind" in
        CONFIG) task_dir=$XDG_CONFIG_HOME ;;
        DATA) task_dir=$XDG_DATA_HOME ;;
        CACHE) task_dir=$XDG_CACHE_HOME ;;
        STATE) task_dir=$XDG_STATE_HOME ;;
    esac
    test "$(cat "$task_dir/jarvis/upgrade-sentinel")" = "keep-$task_kind"
done
test ! -e /usr/bin/jarvis
test ! -e /usr/bin/jarvis-overlay
test ! -e /usr/lib/jarvis
printf '%s\n' 'PASS: eopkg Solus release upgrade, integrity, doctor, removal and XDG data preservation'
