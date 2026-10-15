#!/usr/bin/env bash
# Protege a branch `main` do jarvis contra alterações não autorizadas.
#
# Requer: `gh` autenticado com admin no repo e o repo PÚBLICO (ou plano GitHub
# Pro); em privado free a API responde 403. Pode ser re-rodado: os checks
# obrigatórios já configurados são preservados — o PUT substitui a proteção
# inteira, então lemos o estado atual antes e reenviamos os checks existentes
# (a API exige `required_status_checks` no corpo; mandar o campo como JSON
# null zera os checks, e `-f x=null` manda a string "null" e dá 422, por isso
# o corpo é JSON montado com --input).
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
  echo "  checks obrigatórios existentes seriam preservados"
  exit 0
fi

# Checks obrigatórios atuais: null se a branch ainda não tem proteção (404)
# ou nenhum check configurado. Reconstruímos apenas os campos aceitos no PUT
# (strict + checks[{context, app_id}]), sem os campos de leitura da resposta.
ERR="$(mktemp)"
BODY="$(mktemp)"
trap 'rm -f "$BODY" "$ERR"' EXIT

if ! CHECKS="$(gh api "repos/$REPO/branches/$BRANCH/protection" \
  --jq '.required_status_checks | if . == null then null else
        {strict: .strict,
         checks: [.checks[] | {context: .context} + (if .app_id == null then {} else {app_id: .app_id} end)]}
        end' 2>"$ERR")"; then
  if grep -q "HTTP 404" "$ERR"; then
    CHECKS="null"
  else
    cat "$ERR" >&2
    echo "erro: falha ao consultar a proteção de $REPO@$BRANCH; abortando sem PUT para não zerar os checks obrigatórios" >&2
    exit 1
  fi
fi
CHECKS="${CHECKS:-null}"
cat > "$BODY" <<JSON
{
  "required_status_checks": $CHECKS,
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

echo "proteção aplicada em $REPO@$BRANCH (checks obrigatórios: $CHECKS)"
