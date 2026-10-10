#!/usr/bin/env bash
# Checks the package without a GPU, a model or a network: the harness tests, then the whole diagnostic
# (diagnose.sh) against a scripted fake API (diagnose/fake_api.py) through the api: client, then a rerun
# that must resume without redoing anything. Takes a few minutes. usage: bash diagnose/selftest.sh
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PY=${PYTHON:-python3}
echo "== harness tests"
(cd "$HERE/stageA" && $PY scripts/selfcheck.py | tail -1)
PORT=$($PY -c "import socket; s=socket.socket(); s.bind(('127.0.0.1', 0)); print(s.getsockname()[1])")
$PY "$HERE/diagnose/fake_api.py" "$PORT" & SRV=$!
trap 'kill $SRV 2>/dev/null || true' EXIT
sleep 1
T=$(mktemp -d)
URL="http://127.0.0.1:$PORT/v1"
echo "== diagnostic against the fake API (output in $T)"
SID_API_KEY=fake SEEDS=1 SAMPLES=1 REPLAYS=2 WORKERS=8 \
  bash "$HERE/diagnose.sh" "api:fake-agent@$URL" "api:fake-reader@$URL" "$T/out" > "$T/run1.log" 2>&1 \
  || { tail -30 "$T/run1.log"; echo "selftest FAILED (first run)"; exit 1; }
echo "== rerun (must resume)"
SID_API_KEY=fake SEEDS=1 SAMPLES=1 REPLAYS=2 WORKERS=8 \
  bash "$HERE/diagnose.sh" "api:fake-agent@$URL" "api:fake-reader@$URL" "$T/out" > "$T/run2.log" 2>&1 \
  || { tail -30 "$T/run2.log"; echo "selftest FAILED (rerun)"; exit 1; }
$PY - "$T" <<'PYEOF'
import json, re, sys
t = sys.argv[1]
r = json.load(open(f"{t}/out/report.json"))
log2 = open(f"{t}/run2.log").read()
d = r["discovery"]
assert d["episodes"] == 60 and d["failed"] == 0 and d["readable_summaries"] > 0, d
assert r["rule_flagged"]["restriction"] > 0, r["rule_flagged"]
assert r["ai_confirmed"]["restriction"]["summaries"] > 0, r["ai_confirmed"]
arms = r["replay"]["restriction"]["arms"]
assert arms["original"]["runs"] > 0 and arms["neutral"]["runs"] == arms["original"]["runs"], arms
assert "[discovery] 0 to run" in log2 and "labels unchanged" in log2 and "[replay] 0 to run" in log2, "rerun redid work"
print(f"   episodes {d['episodes']}, readable {d['readable_summaries']}, restriction flags "
      f"{r['rule_flagged']['restriction']}, AI-confirmed {r['ai_confirmed']['restriction']['summaries']}, "
      f"original arm {arms['original']['runs_with_outcome']}/{arms['original']['runs']} runs with a request, "
      f"neutral {arms['neutral']['runs_with_outcome']}/{arms['neutral']['runs']}")
PYEOF
echo "selftest passed"
