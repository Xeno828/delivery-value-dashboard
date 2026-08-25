#!/usr/bin/env bash
#
# What has to be true of a built calculator image before it goes anywhere.
#
# This was inline in the `container` job of .github/workflows/ci.yml, which was
# fine while CI was the only thing that built the image. The weekly rebuild in
# .github/workflows/deploy.yml builds it too — from a base image that has moved
# even when this repository has not — and it must clear the same bar before it
# is deployed. Two copies of these assertions would be two things to keep in
# step, and the first time they disagreed the answer would be "which workflow
# do you believe", which is the failure this repository writes rules about.
#
# So: one implementation, two callers. Run from the repository root, because
# the forecast case reads data/sample-multi-sprint.json.
#
#   bash service/smoke.sh <image-tag>
#
# Exits non-zero on the first failure, with a sentence naming it.

set -euo pipefail

IMAGE="${1:?usage: service/smoke.sh <image-tag>}"
NAME="calc-smoke-$$"
PORT="${SMOKE_PORT:-8080}"

fail() { echo "::error::$1"; exit 1; }
ok()   { echo "  ok — $1"; }

cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "smoke-testing $IMAGE"

# 1. A calculator that came up unauthenticated would look healthy, which is the
#    whole reason the service refuses rather than defaulting to open.
if docker run --rm "$IMAGE" >/dev/null 2>&1; then
  fail "the container started without SERVICE_SHARED_SECRET"
fi
ok "refuses to start with no secret"

# Minted per run rather than written down. A literal here is indistinguishable
# from a real credential to a secret scanner — the security suite flags it — and
# a workflow that needs a hard-coded one is a workflow teaching a bad habit.
CALC_SECRET="$(openssl rand -hex 32)"

# --read-only is kept because the claim is true: the service writes nothing.
# A true claim is a cheap one to make in a security review.
docker run -d --name "$NAME" -p "$PORT:8080" \
  -e SERVICE_SHARED_SECRET="$CALC_SECRET" \
  --read-only --tmpfs /tmp \
  "$IMAGE" >/dev/null

for _ in $(seq 1 30); do
  curl -fsS "http://127.0.0.1:$PORT/healthz" >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS "http://127.0.0.1:$PORT/healthz" >/dev/null || fail "never became healthy"
ok "healthy"

uid="$(docker exec "$NAME" id -u)"
[ "$uid" != "0" ] || fail "running as root"
ok "runs as uid $uid, not root"

code="$(curl -s -o /dev/null -w '%{http_code}' -X POST \
  "http://127.0.0.1:$PORT/v1/forecast" -d '{"dataset":{"issues":[]}}')"
[ "$code" = "401" ] || fail "unauthenticated request got $code, expected 401"
ok "refuses an unauthenticated request"

payload="$(mktemp)"
python3 - > "$payload" <<'EOF'
import json, sys
sys.path.insert(0, "agent/tools")
KEEP = ("key","created","started","resolved","statusCategory",
        "storyPoints","priority","dueDate","flagged","addedMidSprint")
d = json.load(open("data/sample-multi-sprint.json"))
print(json.dumps({"dataset": {
    "issues": [{k: i[k] for k in KEEP if i.get(k) is not None} for i in d["issues"]],
    "meta": d.get("meta", {}), "orgConfig": {}}}))
EOF

curl -fsS -X POST "http://127.0.0.1:$PORT/v1/forecast" \
  -H "Authorization: Bearer $CALC_SECRET" \
  -H 'Content-Type: application/json' \
  --data @"$payload" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['ok'], d
assert d['result']['sprint_completion']['percentiles'], d
assert 'working week' in d['calendar'], d
print('  ok — returns a figure: p85', d['result']['sprint_completion']['percentiles']['85'])
print('  ok — names its calendar:', d['calendar'][:48])"

out="$(mktemp)"
code="$(curl -s -o "$out" -w '%{http_code}' -X POST \
  "http://127.0.0.1:$PORT/v1/forecast" \
  -H "Authorization: Bearer $CALC_SECRET" \
  -H 'Content-Type: application/json' \
  -d '{"dataset":{"issues":[{"key":"A-1","summary":"secret title"}]}}')"
[ "$code" = "400" ] || fail "issue text got $code, expected 400"
grep -q "was not stored" "$out" || { cat "$out"; fail "wrong refusal for issue text"; }
ok "refuses issue text, and says it was not stored"

# The claim the whole architecture rests on. An access log holding issue text is
# a copy of the customer's backlog in a log aggregator, so it is checked against
# a request that deliberately carried some.
if docker logs "$NAME" 2>&1 | grep -q "secret title"; then
  docker logs "$NAME"
  fail "the container logged issue text"
fi
ok "logged no issue text"

echo "all container checks passed"
