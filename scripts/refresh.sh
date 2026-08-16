#!/usr/bin/env bash
# Refresh the dashboard dataset from Jira and/or Asana.
# Credentials come from .env in the repository root (git-ignored).
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a; . ./.env; set +a
else
  echo "No .env found. Copy .env.example to .env and fill it in." >&2
  exit 1
fi

ARGS=()
[ -n "${JIRA_BOARD:-}" ]    && ARGS+=(--jira-board "$JIRA_BOARD")
[ -n "${ASANA_PROJECT:-}" ] && ARGS+=(--asana-project "$ASANA_PROJECT")
if [ ${#ARGS[@]} -eq 0 ]; then
  echo "Set JIRA_BOARD and/or ASANA_PROJECT in .env" >&2
  exit 1
fi

python3 scripts/fetch_delivery_data.py \
  "${ARGS[@]}" \
  --team "${TEAM_NAME:-}" --org "${ORG_NAME:-}" \
  --out data/dashboard-data.json

echo
echo "Wrote data/dashboard-data.json"
echo "Load it: drag onto the dashboard's upload panel, or run 'make serve' and open"
echo "  http://localhost:8000/dist/delivery-value-dashboard.html?data=../data/dashboard-data.json"
