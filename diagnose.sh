#!/usr/bin/env bash
# Handoff-summary diagnostic for one model: discovery on the 60 held-out templates, AI readers on every
# rule-flagged summary, same-snapshot replay of the confirmed sources, report.
#
# usage: bash diagnose.sh MODEL_SPEC READER_SPEC OUT_DIR
#   MODEL_SPEC   the model under test: api:<model-id>@<base-url> (hosted API) or
#                openai:<served-name>@http://localhost:8000/v1 (your own vLLM/SGLang server, paper presets)
#   READER_SPEC  the model that reads the summaries (two readers: seeds 1 and 2, or READER_B)
#   OUT_DIR      new or earlier output folder; a rerun with the same arguments resumes where it stopped
# environment (defaults in brackets):
#   SID_API_KEY  key for MODEL_SPEC; READER_API_KEY key for the readers [SID_API_KEY]
#   READER_B [READER_SPEC]  SEED_OFFSET [5]  SEEDS [5]  SAMPLES [2]  REPLAYS [4]  WORKERS [4]
#   EXTRA_ARGS   harness options for discovery and replay, e.g. "--max-tokens 16384 --summary-max-tokens 16384"
#   READER_ARGS  reader options, e.g. "--max-tokens 16384" for a reasoning model as reader
#   ALLOW_ERRORS=1  go on although some episodes failed or some labels are unreadable
set -euo pipefail
if [ $# -ne 3 ]; then sed -n '2,15p' "$0"; exit 2; fi
MODEL=$1; READER=$2
case "$MODEL" in
  vllm:*) echo "Use openai:${MODEL#vllm:} instead: the same client and sampling presets. The vllm: spec is for the"
          echo "paper's cluster runs, which must record the model files and the server (see stageA/README.md)."; exit 2;;
esac
mkdir -p "$3"; OUT=$(cd "$3" && pwd)
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
READER_B=${READER_B:-$READER}
SEED_OFFSET=${SEED_OFFSET:-5}; SEEDS=${SEEDS:-5}; SAMPLES=${SAMPLES:-2}; REPLAYS=${REPLAYS:-4}; WORKERS=${WORKERS:-4}
EXTRA_ARGS=${EXTRA_ARGS:-}; READER_ARGS=${READER_ARGS:-}
PY=${PYTHON:-python3}
DISC=$OUT/runs/disc_target; REP=$OUT/runs/replay_target; LAB=$OUT/labels
mkdir -p "$OUT/runs" "$LAB"
log() { echo; echo "== $(date -u +%H:%M:%S) $*"; }

log "1/5 discovery: ${MODEL%%@*}, test split, instance seeds $SEED_OFFSET-$((SEED_OFFSET + SEEDS - 1)), $SAMPLES run(s) each"
# shellcheck disable=SC2086
$PY "$HERE/stageA/scripts/run_discovery.py" --model "$MODEL" --split test --seed-offset "$SEED_OFFSET" \
  --seeds "$SEEDS" --samples "$SAMPLES" --workers "$WORKERS" --out "$DISC" $EXTRA_ARGS
# the sheets are built from a copy without the half-written line a crash can leave behind
NFAIL=$($PY "$HERE/diagnose/clean_runs.py" "$DISC/trajectories.jsonl" "$OUT/runs/sheet_input/disc_target")
if [ "$NFAIL" != 0 ] && [ "${ALLOW_ERRORS:-0}" != 1 ]; then
  echo "$NFAIL episodes failed (see the 'error' rows in $DISC/trajectories.jsonl)."
  echo "Run the same command again to retry them; finished episodes are skipped. ALLOW_ERRORS=1 goes on without them."
  exit 1
fi

log "2/5 reading sheets of the rule-flagged summaries"
# the item ids depend on the discovery file: if the sheets exist already, they must come out the same
NEW=$(mktemp -d)
CODE="$HERE/stageA" ANN="$HERE/annotation" RUNS="$OUT/runs/sheet_input" DISC="disc_{m}" MODELS=target PREFIXES=U,V \
  SEEDS=20261101,20261102 OUT="$NEW/diag" $PY -I "$HERE/analysis/f3_sheet.py"
for k in auth restr; do
  for f in "diag_${k}_sheet.txt" "diag_${k}_key.json"; do
    if [ -e "$LAB/$f" ]; then
      cmp -s "$LAB/$f" "$NEW/$f" || { echo "The discovery runs changed after $LAB/$f was written; its labels no longer fit. Use a new OUT_DIR."; exit 1; }
    else
      cp "$NEW/$f" "$LAB/$f"
    fi
  done
done
rm -r "$NEW"
cp "$HERE/stageA/docs/AI_LABEL_GUIDE.md" "$LAB/"

if [ -e "$LAB/AI_LABELS_SHA256.txt" ]; then
  log "3/5 labels were hashed earlier; checking them instead of reading again"
  $PY - "$LAB" <<'PYEOF'
import hashlib, sys
d = sys.argv[1]
for line in open(f"{d}/AI_LABELS_SHA256.txt"):
    if line.startswith("hashed") or not line.strip():
        continue
    h, n = line.split()
    if hashlib.sha256(open(f"{d}/{n}", "rb").read()).hexdigest() != h:
        sys.exit(f"{n} changed after the labels were hashed; use a new OUT_DIR")
print("   labels unchanged")
PYEOF
else
  log "3/5 two AI readers: ${READER%%@*} (seed 1), ${READER_B%%@*} (seed 2)"
  for r in a b; do
    if [ $r = a ]; then SPEC=$READER; SEED=1; else SPEC=$READER_B; SEED=2; fi
    # shellcheck disable=SC2086
    SID_API_KEY=${READER_API_KEY:-${SID_API_KEY:-EMPTY}} $PY "$HERE/diagnose/ai_reader.py" --reader "$SPEC" --seed $SEED \
      --workers "$WORKERS" --out "$LAB/ai_$r.jsonl" $READER_ARGS "$LAB/diag_auth_sheet.txt" "$LAB/diag_restr_sheet.txt"
  done
  $PY - "$LAB" "${READER%%@*}" "${READER_B%%@*}" <<'PYEOF'
import json, sys
d, a, b = sys.argv[1:4]
json.dump({"a": {"spec": a, "seed": 1}, "b": {"spec": b, "seed": 2}}, open(f"{d}/readers.json", "w"), indent=1)
PYEOF
  NUNREAD=$(cat "$LAB/ai_a.jsonl" "$LAB/ai_b.jsonl" | grep -c '"label": "unreadable"' || true)
  if [ "$NUNREAD" != 0 ] && [ "${ALLOW_ERRORS:-0}" != 1 ]; then
    echo "$NUNREAD labels are unreadable (see labels/ai_*.jsonl.raw.jsonl). Run the same command again to retry them,"
    echo "perhaps with READER_ARGS=\"--max-tokens 16384\"; ALLOW_ERRORS=1 goes on and counts them as not confirmed."
    exit 1
  fi
  $PY - "$LAB" <<'PYEOF'
import hashlib, sys, time
d = sys.argv[1]
names = ["ai_a.jsonl", "ai_b.jsonl", "diag_auth_key.json", "diag_restr_key.json", "diag_auth_sheet.txt", "diag_restr_sheet.txt"]
with open(f"{d}/AI_LABELS_SHA256.txt", "w") as f:
    for n in names:
        f.write(f"{hashlib.sha256(open(f'{d}/{n}', 'rb').read()).hexdigest()}  {n}\n")
    f.write(f"hashed {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}, before the replay\n")
PYEOF
fi
$PY "$HERE/diagnose/targets.py" "$LAB" diag target

log "4/5 same-snapshot replay of the AI-confirmed sources ($REPLAYS runs per arm)"
NSRC=$($PY -c "import json, sys; print(len(json.load(open(sys.argv[1]))))" "$LAB/targets_diag_target.json")
if [ "$NSRC" = 0 ]; then
  echo "no AI-confirmed sources: nothing to replay"
else
  # shellcheck disable=SC2086
  $PY "$HERE/stageA/scripts/run_replay.py" --model "$MODEL" --split test --from "$DISC/trajectories.jsonl" \
    --targets-file "$LAB/targets_diag_target.json" \
    --arms original neutral neutral_control delete claim_correct ledger_correct --replays "$REPLAYS" \
    --workers "$WORKERS" --out "$REP" $EXTRA_ARGS
fi

log "5/5 report"
$PY "$HERE/diagnose/report.py" "$OUT"
echo; echo "written: $OUT/report.md and $OUT/report.json"
