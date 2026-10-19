#!/bin/sh
set -eu

task_arch=${1:?XBPS architecture required}
task_repository=${2:?repository kind required}
task_base=${JARVIS_VOID_REPOSITORY_BASE:-https://repo-default.voidlinux.org/current}

case "$task_arch" in
    x86_64) ;;
    x86_64-musl) task_base=$task_base/musl ;;
    aarch64|aarch64-musl) task_base=$task_base/aarch64 ;;
    *) echo "Unsupported Void architecture: $task_arch" >&2; exit 2 ;;
esac

case "$task_repository" in
    main) printf '%s\n' "$task_base" ;;
    bootstrap) printf '%s/bootstrap\n' "$task_base" ;;
    *) echo "Unknown Void repository kind: $task_repository" >&2; exit 2 ;;
esac
