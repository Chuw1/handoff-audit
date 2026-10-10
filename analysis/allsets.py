"""One table of every replay set used in the paper: AI-confirmed sources only.
Sets: dev (v0.3.10 overnight), test (pre-registered replay), F1, F2. usage: python3 -I allsets.py SCRATCH OUT.json"""
import json, sys, collections
from math import comb
S, OUT = sys.argv[1], sys.argv[2]
def sp(a, b):
    n = a + b; k = min(a, b); return min(1, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1
def both_yes(lab_dir, key_file):
    lab = collections.defaultdict(list)
    for r in "abcd":
        for l in open(f"{lab_dir}/ai_{r}.jsonl"):
            x = json.loads(l); lab[x["id"]].append(x["label"])
    return {k["job_id"] for k in json.load(open(key_file)) if lab[k["id"]].count("yes") == 2 and not k.get("control")}
M3 = ("qwen3_8b", "gptoss_20b", "qwen3_14b"); M2 = ("qwen3_8b", "gptoss_20b")
SETS = {
 "dev":  {"restr": (f"{S}/ov310/labels", f"{S}/ov310/labels/restr_key.json", [f"{S}/ov310/raw/runs/replay_v039x_restr_{m}/replay.jsonl" for m in M3]),
          "auth":  (f"{S}/ov310/labels", f"{S}/ov310/labels/auth_key.json", [f"{S}/ov310/raw/runs/replay_v039x_auth_{m}/replay.jsonl" for m in M3])},
 "test": {"restr": (f"{S}/test310/labels", f"{S}/test310/labels/test_restr_key.json", [f"{S}/test310/raw/runs/test_replay_restr_{m}/replay.jsonl" for m in M2]),
          "auth":  (f"{S}/test310/labels", f"{S}/test310/labels/test_auth_key.json", [f"{S}/test310/raw/runs/test_replay_auth_{m}/replay.jsonl" for m in M2])},
 "F1":   {"restr": (f"{S}/test310/labels", f"{S}/test310/labels/test_restr_key.json", [f"{S}/f1f2/raw/runs/test_replay_f1_{m}/replay.jsonl" for m in M2]),
          "auth":  (f"{S}/test310/labels", f"{S}/test310/labels/test_auth_key.json", [f"{S}/f1f2/raw/runs/test_replay_f1_{m}/replay.jsonl" for m in M2])},
 "F2":   {"restr": (f"{S}/f1f2/labels", f"{S}/f1f2/labels/f2_restr_key.json", [f"{S}/f2r2/raw/runs/test_replay_f2_{m}/replay.jsonl" for m in M2]),
          "auth":  (f"{S}/f1f2/labels", f"{S}/f1f2/labels/f2_auth_key.json", [f"{S}/f2r2/raw/runs/test_replay_f2_{m}/replay.jsonl" for m in M2])},
}
F = {"confirm": lambda r: r["n_confirm_requests"] > 0, "exec": lambda r: r["n_executed_unauth"] > 0,
     "viol": lambda r: bool(r["any_violation"]), "success": lambda r: bool(r["success"])}
out = {}
for sname, kinds in SETS.items():
    for kind, (L, K, paths) in kinds.items():
        yes = both_yes(L, K)
        per = collections.defaultdict(lambda: collections.defaultdict(list))
        for p in paths:
            for l in open(p):
                r = json.loads(l)
                if r.get("error") or r.get("run_error") or r["job_id"].startswith("replay-control"): continue
                if r["source_job_id"] in yes: per[r["source_job_id"]][r["arm"]].append(r)
        arms = sorted({a for v in per.values() for a in v})
        res = {"sources": len(per)}
        for a in arms:
            ks = [k for k in per if per[k][a] and per[k]["original"]]
            row = {}
            for fn, f in F.items():
                num = sum(sum(map(f, per[k][a])) for k in ks); den = sum(len(per[k][a]) for k in ks)
                d = [sum(map(f, per[k]["original"])) / len(per[k]["original"]) - sum(map(f, per[k][a])) / len(per[k][a]) for k in ks]
                dn = sum(x > 1e-12 for x in d); up = sum(x < -1e-12 for x in d)
                row[fn] = [num, den, dn, up, sp(dn, up)]
            res[a] = row
        out[f"{sname}/{kind}"] = res
        main = "confirm" if kind == "restr" else "exec"
        print(f"== {sname}/{kind}: {len(per)} sources")
        for a in arms:
            num, den, dn, up, p = res[a][main]
            extra = f"  confirm {res[a]['confirm'][0]}/{den}" if kind == "auth" else f"  viol {res[a]['viol'][0]}/{den} success {res[a]['success'][0]}/{den}"
            print(f"   {a:15s} {main} {num}/{den}  down {dn} up {up} p={p:.3g}{extra}")
json.dump(out, open(OUT, "w"), indent=1)
