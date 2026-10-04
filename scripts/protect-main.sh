#!/usr/bin/env bash
# Protege a branch `main` do jarvis contra alterações não autorizadas.
#
# Requer: `gh` autenticado com admin no repo e o repo PÚBLICO (ou plano GitHub
# Pro); em privado free a API responde 403. Aplique após publicar e rode só
# quando a proteção ainda não existir (a API PUT exige required_status_checks
# como JSON null; a forma `-f x=null` manda a string "null" e dá 422).
#
# Uso:
#   ./scripts/protect-main.sh            # aplica a proteção
#   ./scripts/protect-main.sh --dry-run  # só mostra o que faria
set -euo pipefail

REPO="${REPO:-GuilhermeBn198/jarvis}"
BRANCH="${BRANCH:-main}"

if [ "${1:-}" = "--dry-run" ]; then
  echo "aplicaria proteção em $REPO@$BRANCH:"
  echo "  exigir PR com 1 revisão (code owners), sem push direto,"
  echo "  sem force-push, sem delete, exigir conversas resolvidas"
  exit 0
fi

BODY="$(mktemp)"
trap 'rm -f "$BODY"' EXIT
cat > "$BODY" <<'JSON'
{
  "required_status_checks": null,
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "required_approving_review_count": 1
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON

gh api -X PUT "repos/$REPO/branches/$BRANCH/protection" \
  -H "Accept: application/vnd.github+json" \
  --input "$BODY" >/dev/null

echo "proteção aplicada em $REPO@$BRANCH"
