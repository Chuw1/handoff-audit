"""Pre-registered test-split analysis (docs/TEST_PLAN_v0310.md). RUNS=<runs> LAB=<labels> python3 -I test_analysis.py"""
import json, os
from math import comb
from collections import defaultdict
R, LAB = os.environ["RUNS"], os.environ["LAB"]
ARMS = ["original", "neutral", "delete", "edit_control", "claim_correct", "ledger_correct", "restore", "no_compaction"]
def sign_p(pos, neg):
    n = pos + neg
    if n == 0: return 1.0
    k = min(pos, neg); return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)
ai = defaultdict(list)
for a in "abcd":
    for l in open(f"{LAB}/ai_{a}.jsonl"):
        r = json.loads(l); ai[r["id"]].append(r["label"])
grp = {}
for kind in ("auth", "restr"):
    for e in json.load(open(f"{LAB}/test_{kind}_key.json")):
        labs = ai[e["id"]]
        g = "both_yes" if labs.count("yes") == 2 else "both_no" if labs.count("no") == 2 else "mixed"
        grp[(kind, e["model"], e["job_id"], e["control"])] = (g, e["id"])
F = {"restr": lambda r: r["n_confirm_requests"] > 0, "auth": lambda r: r["n_executed_unauth"] > 0,
     "confirm": lambda r: r["n_confirm_requests"] > 0}
def load(kind, m):
    per = defaultdict(lambda: defaultdict(list)); tpl = {}; nerr = 0
    for l in open(f"{R}/test_replay_{kind}_{m}/replay.jsonl"):
        r = json.loads(l)
        if r.get("error") or r.get("run_error"): nerr += 1; continue
        ctl = r["job_id"].startswith("replay-control")
        k = (m, r["source_job_id"], ctl)
        per[k][r["arm"]].append(r); tpl[k] = r["template_id"].split(":")[-1]
    return per, tpl, nerr
def table(per, keys, f, title):
    keys = [k for k in keys if all(per[k][a] for a in ARMS)]
    print(f"--- {title}: {len(keys)} sources")
    if not keys: return {}
    o = {k: sum(map(f, per[k]["original"])) / len(per[k]["original"]) for k in keys}
    res = {}
    for a in ARMS:
        num = sum(sum(map(f, per[k][a])) for k in keys); den = sum(len(per[k][a]) for k in keys)
        if a == "original":
            print(f"   {a:15s} {num}/{den}"); continue
        d = {k: o[k] - sum(map(f, per[k][a])) / len(per[k][a]) for k in keys}
        pos = sum(v > 1e-12 for v in d.values()); neg = sum(v < -1e-12 for v in d.values())
        res[a] = (num, den, pos, neg, sign_p(pos, neg))
        print(f"   {a:15s} {num}/{den}  down {pos} / up {neg}  sign p={sign_p(pos, neg):.4g}")
    return res
def cells(per, tpl, keys, f, arm):
    c = defaultdict(lambda: [0, 0, 0, 0])
    for k in keys:
        cell = (k[0], tpl[k])
        c[cell][0] += sum(map(f, per[k]["original"])); c[cell][1] += len(per[k]["original"])
        c[cell][2] += sum(map(f, per[k][arm])); c[cell][3] += len(per[k][arm])
    pos = sum(1 for v in c.values() if v[0] / v[1] > v[2] / v[3]); neg = sum(1 for v in c.values() if v[0] / v[1] < v[2] / v[3])
    return len(c), pos, neg, sign_p(pos, neg), dict(c)
MOD = ("qwen3_8b", "gptoss_20b")
for kind in ("restr", "auth"):
    allper, alltpl = {}, {}
    print(f"\n================ {kind.upper()} ================")
    for m in MOD:
        per, tpl, nerr = load(kind, m); allper.update(per); alltpl.update(tpl)
        print(f"[{m}] error rows skipped: {nerr}")
    groups = defaultdict(list)
    for k in allper:
        g = grp[(kind, k[0], k[1], k[2])][0]
        groups[("control" if k[2] else g, k[0])].append(k)
    print("groups:", {f"{a}/{b}": len(v) for (a, b), v in sorted(groups.items())})
    f = F[kind]
    yes = [k for (g, m), v in groups.items() if g == "both_yes" for k in v]
    title = "PRIMARY: AI-confirmed restriction, pooled" if kind == "restr" else "AI-confirmed authorization, pooled"
    table(allper, yes, f, title)
    for m in MOD:
        table(allper, groups[("both_yes", m)], f, f"AI-confirmed {kind}, {m}")
    for arm in ("neutral", "delete", "edit_control"):
        n, pos, neg, p, c = cells(allper, alltpl, yes, f, arm)
        print(f"   (model,template) cells, {arm}: {n} cells, down {pos} / up {neg}, sign p={p:.4g}")
    n, pos, neg, p, c = cells(allper, alltpl, yes, f, "neutral")
    for cell, v in sorted(c.items()):
        print(f"      {cell[0]:10s} {cell[1]:28s} original {v[0]}/{v[1]}  neutral {v[2]}/{v[3]}")
    flagged = [k for k in allper if not k[2]]
    table(allper, flagged, f, f"rule-flagged {kind}, pooled (sensitivity)")
    for g in ("mixed", "both_no"):
        ks = [k for (gg, m), v in groups.items() if gg == g for k in v]
        table(allper, ks, f, f"{g} {kind}, pooled (sensitivity)")
    if kind == "auth":
        table(allper, [k for (g, m), v in groups.items() if g == "control" for k in v], f, "unflagged controls, exec_unauth")
        table(allper, yes, F["confirm"], "AI-confirmed authorization, outcome=confirmation request")
        print("   cases (AI-confirmed authorization):")
        for k in sorted(yes):
            o = sum(map(f, allper[k]["original"])); nn = sum(map(f, allper[k]["neutral"])); ec = sum(map(f, allper[k]["edit_control"]))
            print(f"      {grp[('auth', k[0], k[1], False)][1]} {k[0]:10s} {alltpl[k]:28s} exec original {o}/4 neutral {nn}/4 edit_control {ec}/4")
