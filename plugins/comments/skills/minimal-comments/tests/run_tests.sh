#!/usr/bin/env bash
#
# The auditor has to find what it should and stay quiet about what it should not. The second half
# matters more: a checker that flags correct code is one somebody adds --skip to within a week.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

PY="${PYTHON:-python3}"
AUDIT="../scripts/audit_comments.py"

# Categories the offenders fixture is built to trip. Add a rule, add a case, add it here.
EXPECTED=(todo commented_code banner restates)

failures=0

echo "==> offenders should trip every category they break"
report=$("$PY" "$AUDIT" fixtures/offenders --format json || true)
for category in "${EXPECTED[@]}"; do
    if echo "$report" | "$PY" -c "
import json, sys
sys.exit(0 if any(n['category'] == '$category' for n in json.load(sys.stdin)['notes']) else 1)
"; then
        echo "    ok    $category"
    else
        echo "    MISS  $category not reported, so that check has stopped working"
        failures=$((failures + 1))
    fi
done

echo "==> clean should report nothing"
clean=$("$PY" "$AUDIT" fixtures/clean --format json || true)
count=$(echo "$clean" | "$PY" -c "import json,sys; d=json.load(sys.stdin); print(d['failing'] + d['advisory'])")
if [ "$count" = "0" ]; then
    echo "    ok    no false positives"
else
    echo "    FALSE POSITIVES ($count):"
    echo "$clean" | "$PY" -c "
import json, sys
for n in json.load(sys.stdin)['notes']:
    print(f\"      {n['category']:<18} {n['path']}:{n['line']}  {n['text'][:70]}\")
"
    failures=$((failures + count))
fi

echo "==> a generated file is nobody's to answer for"
if echo "$clean" | "$PY" -c "
import json, sys
notes = json.load(sys.stdin)['notes']
sys.exit(1 if any('generated' in n['path'] for n in notes) else 0)
"; then
    echo "    ok    skipped"
else
    echo "    FAIL  reported a file marked DO NOT EDIT"
    failures=$((failures + 1))
fi

echo
[ "$failures" -eq 0 ] && echo "all good: ${#EXPECTED[@]} categories caught, no false positives" \
                      || echo "$failures problem(s)"
exit "$failures"
