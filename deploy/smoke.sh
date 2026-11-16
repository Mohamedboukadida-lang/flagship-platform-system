#!/usr/bin/env bash
# Smoke test of a running deployment: the M0 exit gate in script form.
#   deploy/smoke.sh https://demo.example.org
# Against the local stack (make up, make migrate seed run):
#   API_URL=http://localhost:8000 AUTH_URL=http://localhost:8080/auth SMOKE_PASSWORD=demo_dev deploy/smoke.sh
# With SMOKE_PASSWORD set it also logs in as a demo user and checks the tenant boundary.
set -euo pipefail

BASE="${1:-}"
API_URL="${API_URL:-$BASE/api}"
AUTH_URL="${AUTH_URL:-$BASE/auth}"
USER_NAME="${SMOKE_USER:-alice}"
TENANT="${SMOKE_TENANT:-acme}"
OTHER_TENANT="${SMOKE_OTHER_TENANT:-globex}"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}
status() { curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "$@" 2> /dev/null || true; }
field() { python3 2> /dev/null -c 'import json, sys; d = json.load(sys.stdin); [d := d[k] for k in sys.argv[1:]]; print(d)' "$@"; }

# A fresh deployment needs a moment for the ingress and its certificate.
for attempt in $(seq 1 36); do
  [ "$(status "$API_URL/healthz")" = 200 ] && break
  [ "$attempt" = 36 ] && fail "$API_URL/healthz did not return 200 within 3 minutes"
  sleep 5
done

[ "$(status "$API_URL/readyz")" = 200 ] || fail "readyz: a store is unreachable"
[ "$(status "$API_URL/v1/me")" = 401 ] || fail "anonymous /v1/me must be 401"

ISSUER=$(curl -sS --max-time 15 "$AUTH_URL/realms/lotse/.well-known/openid-configuration" | field issuer) \
  || fail "identity provider is not answering"
[ "$ISSUER" = "$AUTH_URL/realms/lotse" ] || fail "issuer is $ISSUER, expected $AUTH_URL/realms/lotse"

if [ -z "${SMOKE_PASSWORD:-}" ]; then
  echo "ok: health, readiness, 401 for anonymous, issuer (set SMOKE_PASSWORD to test a login)"
  exit 0
fi

TOKEN=$(curl -sS --max-time 15 "$AUTH_URL/realms/lotse/protocol/openid-connect/token" \
  -d grant_type=password -d client_id=lotse-cli -d "username=$USER_NAME" \
  --data-urlencode "password=$SMOKE_PASSWORD" | field access_token) || fail "login as $USER_NAME"

GOT=$(curl -sS --max-time 15 "$API_URL/v1/me" -H "Authorization: Bearer $TOKEN" -H "X-Tenant: $TENANT" \
  | field tenant slug) || fail "/v1/me as $USER_NAME in $TENANT"
[ "$GOT" = "$TENANT" ] || fail "/v1/me returned tenant $GOT, expected $TENANT"

DENIED=$(status "$API_URL/v1/me" -H "Authorization: Bearer $TOKEN" -H "X-Tenant: $OTHER_TENANT")
[ "$DENIED" = 403 ] || fail "$USER_NAME reached $OTHER_TENANT (status $DENIED)"

echo "ok: $USER_NAME logged in, got tenant $GOT, and was refused in $OTHER_TENANT"
