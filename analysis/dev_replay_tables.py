"""Per-source paired replay tables for the v0.3.10 overnight replays, by label layer.
RUNS=<runs dir> LAB=<labels dir> python3 -I tiers310.py"""
import json, os
from math import comb
from collections import defaultdict
R, LAB = os.environ["RUNS"], os.environ["LAB"]
ARMS = ["original", "neutral", "delete", "edit_control", "claim_correct", "ledger_correct", "restore", "no_compaction"]
def sign_p(pos, neg):
    n = pos + neg
    if n == 0: return 1.0
    k = min(pos, neg); return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)
ai = {}
for a in "abcd":
    for l in open(f"{LAB}/ai_{a}.jsonl"):
        r = json.loads(l); ai.setdefault(r["id"], []).append(r["label"])
key = {}
for k in ("auth", "restr"):
    for e in json.load(open(f"{LAB}/{k}_key.json")):
        labs = ai[e["id"]]
        key[(e["model"], e["job_id"])] = ("both_yes" if labs.count("yes") == 2 else
                                          "both_no" if labs.count("no") == 2 else "mixed")
def load(path, model):
    per = defaultdict(lambda: defaultdict(list)); ctl = defaultdict(lambda: defaultdict(list)); meta = {}
    nerr = 0
    for l in open(path):
        r = json.loads(l)
        if r.get("error") or r.get("run_error"):
            nerr += 1; continue
        d = ctl if r["job_id"].startswith("replay-control") else per
        d[r["source_job_id"]][r["arm"]].append(r)
        meta[r["source_job_id"]] = r["template_id"]
    return per, ctl, meta, nerr
F = {"confirm": lambda r: r["n_confirm_requests"] > 0,
     "exec_unauth": lambda r: r["n_executed_unauth"] > 0,
     "any_violation": lambda r: bool(r["any_violation"])}
def table(per, srcs, out, title):
    f = F[out]
    srcs = [s for s in srcs if all(per[s][a] for a in ARMS)]
    print(f"--- {title}: {len(srcs)} sources, outcome={out}")
    if not srcs: return
    o = {s: sum(map(f, per[s]["original"])) / len(per[s]["original"]) for s in srcs}
    for a in ARMS:
        num = sum(sum(map(f, per[s][a])) for s in srcs); den = sum(len(per[s][a]) for s in srcs)
        if a == "original":
            print(f"   {a:15s} {num}/{den}"); continue
        d = {s: o[s] - sum(map(f, per[s][a])) / len(per[s][a]) for s in srcs}
        pos = sum(v > 1e-12 for v in d.values()); neg = sum(v < -1e-12 for v in d.values())
        print(f"   {a:15s} {num}/{den}  down {pos} / up {neg}  sign p={sign_p(pos, neg):.4g}")
MOD = {"qwen3_8b": "Qwen3-8B", "gptoss_20b": "gpt-oss-20b", "qwen3_14b": "Qwen3-14B"}
for kind, out_main in (("auth", "exec_unauth"), ("restr", "confirm")):
    for m in MOD:
        per, ctl, meta, nerr = load(f"{R}/replay_v039x_{kind}_{m}/replay.jsonl", m)
        print(f"\n===== {kind} {MOD[m]}  (error rows skipped: {nerr})")
        groups = defaultdict(list)
        for s in per: groups[key[(m, s)]].append(s)
        print("   AI labels:", {g: len(v) for g, v in groups.items()})
        outs = [out_main] + (["any_violation", "confirm"] if kind == "auth" else [])
        for out in outs:
            table(per, list(per), out, f"{MOD[m]} {kind} RULE-flagged (all)")
            for g in ("both_yes", "mixed", "both_no"):
                if groups[g]: table(per, groups[g], out, f"{MOD[m]} {kind} AI {g}")
        if ctl:
            table(ctl, list(ctl), out_main, f"{MOD[m]} {kind} unflagged controls")
