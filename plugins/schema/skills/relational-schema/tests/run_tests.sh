#!/usr/bin/env bash
#
# Proves the checker finds what it should and stays quiet about what it should not.
#
#   ./run_tests.sh
#
# Spins up a throwaway PostgreSQL, loads two fixtures and asserts against both:
#
#   violations.sql  every rule the catalogue can check, broken once, so a check that
#                   silently stopped working is visible as a missing ID
#   conforming.sql  a correct schema, which must produce zero failures - a checker that
#                   cries wolf is one somebody adds --skip to within a week
#
# Needs docker and python with psycopg. PGPORT and IMAGE can be overridden.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

PORT="${PGPORT:-55999}"
IMAGE="${IMAGE:-postgres:18-alpine}"
CONTAINER="schema-conformance-test"
PY="${PYTHON:-python3}"

# Every rule ID the violations fixture is built to trip. Add a rule, add a case, add it here.
EXPECTED=(K1 K3 K6 T3 C1 C5 D2 M1 M3 L5 U1)

cleanup() { docker rm -f "$CONTAINER" >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "==> starting $IMAGE on :$PORT"
cleanup
docker run -d --name "$CONTAINER" \
    -e POSTGRES_PASSWORD=test -e POSTGRES_DB=violations \
    -p "$PORT:5432" "$IMAGE" >/dev/null

# The image runs a temporary server on the unix socket while it initialises, so both pg_isready
# and a socket query answer before the real one exists. Only the finished server listens on TCP.
for _ in $(seq 60); do
    docker exec "$CONTAINER" psql -q -h 127.0.0.1 -U postgres -tAc 'select 1' >/dev/null 2>&1 && break
    sleep 1
done

docker exec "$CONTAINER" psql -q -h 127.0.0.1 -U postgres -c 'create database conforming' >/dev/null

url() { echo "postgresql://postgres:test@127.0.0.1:$PORT/$1"; }

echo "==> loading fixtures"
docker exec -i "$CONTAINER" psql -q -h 127.0.0.1 -U postgres -d violations < fixtures/violations.sql
docker exec -i "$CONTAINER" psql -q -h 127.0.0.1 -U postgres -d conforming < fixtures/conforming.sql

failures=0

echo "==> violations.sql should trip every rule it breaks"
report=$("$PY" ../scripts/verify_schema.py --url "$(url violations)" \
    --config fixtures/schema-conventions.toml --format json || true)

for rule in "${EXPECTED[@]}"; do
    if echo "$report" | "$PY" -c "
import json, sys
findings = json.load(sys.stdin)['findings']
sys.exit(0 if any(f['rule'] == '$rule' and f['level'] == 'fail' for f in findings) else 1)
"; then
        echo "    ok    $rule"
    else
        echo "    MISS  $rule was not reported, so that check has stopped working"
        failures=$((failures + 1))
    fi
done

echo "==> conforming.sql should report nothing"
clean=$("$PY" ../scripts/verify_schema.py --url "$(url conforming)" \
    --config fixtures/conforming.toml --format json || true)

count=$(echo "$clean" | "$PY" -c "import json,sys; print(json.load(sys.stdin)['failed'])")
if [ "$count" = "0" ]; then
    echo "    ok    no false positives"
else
    echo "    FALSE POSITIVES ($count):"
    echo "$clean" | "$PY" -c "
import json, sys
for f in json.load(sys.stdin)['findings']:
    if f['level'] == 'fail':
        print(f\"      {f['rule']:<5} {f['subject']}: {f['detail']}\")
"
    failures=$((failures + count))
fi

echo
if [ "$failures" -eq 0 ]; then
    echo "all good: ${#EXPECTED[@]} rules caught, no false positives"
else
    echo "$failures problem(s)"
fi
exit "$failures"
