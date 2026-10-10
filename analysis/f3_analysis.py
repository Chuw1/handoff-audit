"""Analysis of a targets-file replay (F1 exploratory, F2 confirmatory; docs/FOLLOWUP_PLAN_v03101.md).
usage: python3 -I tf_analysis.py RUNS TAG TARGETS_DIR [OLD_RUNS]
  RUNS/test_replay_{TAG}_{m}/replay.jsonl, TARGETS_DIR/targets_{TAG}_{m}.json
  OLD_RUNS (optional, F1 only): the earlier test replay, to split sources by whether F1 edits more sentences."""
import json, sys, os
from math import comb
from collections import defaultdict
R, TAG, TD = sys.argv[1], sys.argv[2], sys.argv[3]
OLD = sys.argv[4] if len(sys.argv) > 4 else None
MOD = tuple(os.environ.get("MODELS", "qwen3_8b,gptoss_20b").split(","))
ARMS = ["original", "neutral", "neutral_control", "delete", "claim_correct", "ledger_correct", "no_compaction"]
if os.environ.get("RESTORE"): ARMS.insert(-1, "restore")  # F3 adds the restore arm
F = {"confirm": lambda r: r["n_confirm_requests"] > 0, "exec": lambda r: r["n_executed_unauth"] > 0,
     "any_viol": lambda r: bool(r["any_violation"]), "success": lambda r: bool(r["success"])}

def sign_p(pos, neg):
    n = pos + neg
    if n == 0: return 1.0
    k = min(pos, neg); return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)

per = defaultdict(lambda: defaultdict(list)); tpl = {}; typ = {}; nerr = 0; tgt = {}
for m in MOD:
    tf = json.load(open(f"{TD}/targets_{TAG}_{m}.json"))
    for l in open(f"{R}/test_replay_{TAG}_{m}/replay.jsonl"):
        r = json.loads(l)
        if r.get("error") or r.get("run_error"): nerr += 1; continue
        k = (m, r["source_job_id"])
        per[k][r["arm"]].append(r); tpl[k] = r["template_id"].split(":")[-1]
        typ[k] = tf[r["source_job_id"]]["types"]; tgt[k] = tf[r["source_job_id"]]["targets"]
print(f"error rows skipped: {nerr}; sources: {len(per)}")

def table(keys, f, title, arms=ARMS):
    keys = [k for k in keys if all(per[k][a] for a in arms)]
    print(f"--- {title}: {len(keys)} sources")
    if not keys: return
    o = {k: sum(map(f, per[k]["original"])) / len(per[k]["original"]) for k in keys}
    for a in arms:
        num = sum(sum(map(f, per[k][a])) for k in keys); den = sum(len(per[k][a]) for k in keys)
        if a == "original": print(f"   {a:15s} {num}/{den}"); continue
        d = [o[k] - sum(map(f, per[k][a])) / len(per[k][a]) for k in keys]
        pos = sum(v > 1e-12 for v in d); neg = sum(v < -1e-12 for v in d)
        print(f"   {a:15s} {num}/{den}  down {pos} / up {neg}  sign p={sign_p(pos, neg):.4g}")

def vs(keys, f, a, b, title):
    """Paired sign test, arm a vs arm b (b plays the role of the reference)."""
    keys = [k for k in keys if per[k][a] and per[k][b]]
    d = [sum(map(f, per[k][b])) / len(per[k][b]) - sum(map(f, per[k][a])) / len(per[k][a]) for k in keys]
    pos = sum(v > 1e-12 for v in d); neg = sum(v < -1e-12 for v in d)
    print(f"   {title}: {a} lower than {b} in {pos}, higher in {neg}, sign p={sign_p(pos, neg):.4g}")

def cells(keys, f, arm):
    c = defaultdict(lambda: [0, 0, 0, 0])
    for k in keys:
        v = c[(k[0], tpl[k])]
        v[0] += sum(map(f, per[k]["original"])); v[1] += len(per[k]["original"])
        v[2] += sum(map(f, per[k][arm])); v[3] += len(per[k][arm])
    pos = sum(1 for v in c.values() if v[0] / v[1] > v[2] / v[3]); neg = sum(1 for v in c.values() if v[0] / v[1] < v[2] / v[3])
    return len(c), pos, neg, sign_p(pos, neg), dict(c)

for kind, t, f, label in (("restriction", "invented_restriction", F["confirm"], "confirmation request"),
                          ("authorization", "invented_authorization", F["exec"], "executed unauthorized action")):
    keys = sorted(k for k in per if t in typ[k])
    print(f"\n================ {kind.upper()} (outcome: {label}) ================")
    table(keys, f, f"{kind}, pooled")
    for m in MOD: table([k for k in keys if k[0] == m], f, f"{kind}, {m}")
    for arm in ("neutral", "neutral_control", "delete"):
        n, pos, neg, p, c = cells(keys, f, arm)
        print(f"   (model,template) cells, {arm}: {n} cells, down {pos} / up {neg}, sign p={p:.4g}")
    n, pos, neg, p, c = cells(keys, f, "neutral")
    for cell, v in sorted(c.items()):
        print(f"      {cell[0]:10s} {cell[1]:30s} original {v[0]}/{v[1]}  neutral {v[2]}/{v[3]}")
    vs(keys, f, "neutral", "neutral_control", f"{kind}, direct")
    vs(keys, f, "delete", "neutral_control", f"{kind}, direct")
    for nm in ("any_viol", "success") + (("confirm",) if kind == "authorization" else ()):
        table(keys, F[nm], f"{kind}, side outcome = {nm}")
        if nm == "confirm":
            vs(keys, F[nm], "neutral_control", "neutral", f"{kind}, confirm, direct")
    if OLD and kind == "restriction":
        old = {}
        for m in MOD:
            for l in open(f"{OLD}/test_replay_restr_{m}/replay.jsonl"):
                r = json.loads(l); old[(m, r["source_job_id"])] = r["targets"]
        more = [k for k in keys if set(tgt[k]) - set(old.get(k, []))]
        same = [k for k in keys if k not in more]
        table(more, f, f"{kind}, F1 edits more sentences than the test replay did")
        table(same, f, f"{kind}, F1 edits the same sentences as the test replay")
