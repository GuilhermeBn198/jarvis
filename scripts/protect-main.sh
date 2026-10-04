#!/usr/bin/env bash
# Protege a branch `main` do jarvis contra alterações não autorizadas.
#
# Requer: `gh` autenticado com escopo de admin no repo. A proteção de branch só
# está disponível em repositório PÚBLICO (ou plano GitHub Pro). Enquanto o repo
# for privado no plano free, a API responde 403 — rode este script após publicar.
#
# Uso:
#   ./scripts/protect-main.sh            # aplica a proteção
#   ./scripts/protect-main.sh --dry-run  # só mostra o que faria
set -euo pipefail

REPO="${REPO:-GuilhermeBn198/jarvis}"
BRANCH="${BRANCH:-main}"

if [ "${1:-}" = "--dry-run" ]; then
  echo "aplicaria proteção em $REPO@$BRANCH:"
  echo "  exigir PR com 1 revisão, sem push direto, sem force-push, sem delete"
  exit 0
fi

gh api -X PUT "repos/$REPO/branches/$BRANCH/protection" \
  -H "Accept: application/vnd.github+json" \
  -f "required_status_checks=null" \
  -F "enforce_admins=false" \
  -F "required_pull_request_reviews[required_approving_review_count]=1" \
  -F "required_pull_request_reviews[dismiss_stale_reviews]=true" \
  -f "restrictions=null" \
  -F "allow_force_pushes=false" \
  -F "allow_deletions=false"

echo "proteção aplicada em $REPO@$BRANCH"
