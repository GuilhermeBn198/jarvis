#!/usr/bin/env bash
set -uo pipefail

task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"

usage() {
    cat <<'EOF'
Uso: scripts/verify-linux.sh [--list]

Executa regressões locais de voz, servidores MCP, GUI, plugins OpenCode e Rust.
Não valida desktops/portais reais, áudio físico nem pacotes de cada distribuição.
--list mostra as etapas sem executá-las.
EOF
}

if [[ ${1-} == --help || ${1-} == -h ]]; then
    usage
    exit 0
fi

if [[ ${1-} == --list ]]; then
    printf '%s\n' \
        '1. voice/.venv/bin/python -m pytest -q voice/tests (ou python3)' \
        '2. python -m pytest -q scripts/tests' \
        '3. python -m pytest -q -c mcp_servers/win_context/pytest.ini mcp_servers/win_context/tests' \
        '4. python -m pytest -q -c mcp_servers/delegate_local/pytest.ini mcp_servers/delegate_local/tests' \
        '5. node --test gui/tests/*.test.mjs' \
        '6. OpenCode: find .opencode (excluding node_modules) -name *.test.ts | node --experimental-strip-types --test' \
        '7. cargo test --locked --manifest-path gui/src-tauri/Cargo.toml' \
        '8. cargo build --locked --release --manifest-path gui/src-tauri/Cargo.toml' \
        'Fora deste verificador: autorização em desktop real, portais e áudio físico ponta a ponta.'
    exit 0
fi

if (($#)); then
    printf 'Opção desconhecida: %s\n' "$1" >&2
    usage >&2
    exit 2
fi

if [[ -x voice/.venv/bin/python ]]; then
    task_python="$task_root/voice/.venv/bin/python"
else
    task_python="$(command -v python3 || true)"
fi
task_node="$(command -v node || true)"
task_cargo="$(command -v cargo || true)"
task_failures=0

run_step() {
    local task_label="$1"
    shift
    printf '\n==> %s\n' "$task_label"
    if "$@"; then
        printf 'PASS: %s\n' "$task_label"
    else
        local task_status=$?
        printf 'FAIL (%s): %s\n' "$task_status" "$task_label" >&2
        task_failures=$((task_failures + 1))
    fi
}

if [[ -z $task_python ]]; then
    printf 'python3 não encontrado\n' >&2
    task_failures=$((task_failures + 1))
else
    run_step 'voice regression suite' "$task_python" -m pytest -q voice/tests
    run_step 'script helper regression suite' "$task_python" -m pytest -q scripts/tests
    run_step 'win_context MCP regression suite' "$task_python" -m pytest -q \
        -c mcp_servers/win_context/pytest.ini mcp_servers/win_context/tests
    run_step 'delegate_local MCP regression suite' "$task_python" -m pytest -q \
        -c mcp_servers/delegate_local/pytest.ini mcp_servers/delegate_local/tests
fi

if [[ -z $task_node ]]; then
    printf 'node não encontrado\n' >&2
    task_failures=$((task_failures + 1))
else
    run_step 'GUI JavaScript regression suite' "$task_node" --test gui/tests/*.test.mjs
    mapfile -t task_opencode_tests < <(
        find .opencode -path .opencode/node_modules -prune -o \
            -type f -name '*.test.ts' -print | sort
    )
    if ((${#task_opencode_tests[@]})); then
        run_step 'OpenCode TypeScript regression suite' "$task_node" \
            --experimental-strip-types --test "${task_opencode_tests[@]}"
    else
        printf 'Nenhum teste TypeScript encontrado em .opencode\n' >&2
        task_failures=$((task_failures + 1))
    fi
fi

if [[ -z $task_cargo ]]; then
    printf 'cargo não encontrado\n' >&2
    task_failures=$((task_failures + 1))
else
    run_step 'Tauri Rust tests' "$task_cargo" test --locked \
        --manifest-path gui/src-tauri/Cargo.toml
    run_step 'Tauri release build' "$task_cargo" build --locked --release \
        --manifest-path gui/src-tauri/Cargo.toml
fi

if ((task_failures)); then
    printf '\n%d etapa(s) falharam. Esta execução não cobre desktop real, portais autorizados, áudio físico ou builds de pacotes por distro.\n' \
        "$task_failures" >&2
    exit 1
fi

printf '\nTodas as regressões locais passaram. Isso não comprova desktop real, portais autorizados, áudio físico ou builds de pacotes por distro.\n'
