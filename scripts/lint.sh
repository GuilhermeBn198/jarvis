#!/usr/bin/env bash
# Lint + format do repo inteiro num comando so.
#
# Python (voice/, mcp_servers/, scripts de .py): ruff (check + format).
# TS/JSON (.opencode): Biome.
#
# Uso:
#   ./scripts/lint.sh          # verifica tudo (nao altera arquivos)
#   ./scripts/lint.sh --fix    # aplica correcoes e formatacao
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIX=0
if [ "${1:-}" = "--fix" ]; then
  FIX=1
fi

# ruff: prefere o binario do venv de voice/ (instalado a partir do
# requirements-dev.txt da raiz); cai para o ruff do PATH se nao existir.
RUFF="${RUFF:-}"
if [ -z "$RUFF" ]; then
  if [ -x "$ROOT/voice/.venv/bin/ruff" ]; then
    RUFF="$ROOT/voice/.venv/bin/ruff"
  elif command -v ruff >/dev/null 2>&1; then
    RUFF="ruff"
  else
    echo "erro: ruff nao encontrado." >&2
    echo "  instale com: voice/.venv/bin/pip install -r requirements-dev.txt" >&2
    exit 1
  fi
fi

# Biome: precisa do binario instalado em .opencode (npm install).
# O --no-install impede o npx de baixar uma versao avulsa na surdina.
run_biome() {
  if [ ! -x "$ROOT/.opencode/node_modules/.bin/biome" ]; then
    echo "erro: biome nao encontrado em .opencode/node_modules." >&2
    echo "  instale com: (cd .opencode && npm ci)" >&2
    exit 1
  fi
  (cd "$ROOT/.opencode" && npx --no-install biome "$@")
}

if [ "$FIX" = 1 ]; then
  # Aplica o que da para corrigir automaticamente e segue em frente mesmo
  # quando sobrar algo manual (no fim o comando falha, se falhou algo).
  FAIL=0
  (cd "$ROOT" && "$RUFF" check --fix .) || FAIL=1
  (cd "$ROOT" && "$RUFF" format .) || FAIL=1
  run_biome check --write . || FAIL=1
  if [ "$FAIL" = 1 ]; then
    echo "lint: sobrou problema que exige correcao manual (acima)" >&2
    exit 1
  fi
else
  (cd "$ROOT" && "$RUFF" check . && "$RUFF" format --check .)
  run_biome check .
fi

echo "lint ok"
