#!/bin/sh
# Retry only DNF failures that indicate transient repository metadata/mirror errors.
set -u

if [ "$#" -eq 0 ]; then
    echo 'Uso: dnf-install-with-metadata-retry.sh dnf-arguments...' >&2
    exit 2
fi

task_log=$(mktemp)
trap 'rm -f "$task_log"' EXIT HUP INT TERM
task_attempt=1
while :; do
    dnf "$@" >"$task_log" 2>&1
    task_result=$?
    cat "$task_log"
    [ "$task_result" -eq 0 ] && exit 0

    if ! grep -Eiq \
        "checksum.*(mismatch|doesn.t match)|failed to download metadata|cannot download repomd.xml|curl error \((6|7|28|35|56|60)\)" \
        "$task_log"; then
        exit "$task_result"
    fi

    if [ "$task_attempt" -ge 3 ]; then
        echo 'DNF repository metadata/mirror failure persisted after 3 attempts.' >&2
        exit "$task_result"
    fi

    task_attempt=$((task_attempt + 1))
    echo "Retrying DNF after transient repository metadata/mirror failure (attempt $task_attempt/3)." >&2
    dnf clean metadata || exit $?
done
