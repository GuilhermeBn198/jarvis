#!/usr/bin/env bash
# Empacota o cerebro do jarvis (voice/) num zipapp `jarvis.pyz`.
#
# O zip NAO embute as dependencias pesadas (faster-whisper etc.): o `jarvis.pyz`
# roda com o Python/venv que ja as tenha em runtime. Isso deixa o pacote leve e
# evita o inferno de empacotar ctranslate2/torch.
#
# Uso:
#   ./scripts/build-pyz.sh              # gera dist/jarvis.pyz
#   ./scripts/build-pyz.sh --check      # so valida o que empacotaria (dry-run)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${OUT:-$ROOT/dist/jarvis.pyz}"
SRC="$ROOT/voice"

if [ ! -d "$SRC" ]; then
  echo "erro: $SRC nao existe" >&2
  exit 1
fi

# Modulos a empacotar: todo .py do voice/ menos testes e caches.
mapfile -t FILES < <(cd "$SRC" && find . -maxdepth 1 -name '*.py' \
  ! -name 'test_*' ! -path './tests/*' | sed 's#^\./##' | sort)

if [ "${#FILES[@]}" -eq 0 ]; then
  echo "erro: nenhum .py encontrado em $SRC" >&2
  exit 1
fi

if [ "${1:-}" = "--check" ]; then
  echo "empacotaria ${#FILES[@]} modulos de $SRC em $OUT:"
  printf '  %s\n' "${FILES[@]}"
  exit 0
fi

mkdir -p "$(dirname "$OUT")"
BUILD="$(mktemp -d)"
trap 'rm -rf "$BUILD"' EXIT

for f in "${FILES[@]}"; do
  cp "$SRC/$f" "$BUILD/$f"
done
# `__main__.py` ja existe em voice/; garante que veio.
if [ ! -f "$BUILD/__main__.py" ]; then
  echo "erro: voice/__main__.py ausente (entrypoint do zipapp)" >&2
  exit 1
fi

python3 -m zipapp "$BUILD" -o "$OUT" -p "/usr/bin/env python3"
echo "gerado: $OUT ($(du -h "$OUT" | cut -f1))"
