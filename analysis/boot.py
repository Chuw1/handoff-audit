"""Per-source effects with (model, template)-cluster bootstrap 95% CIs, for every replay set and arm.
Effect = mean over sources of (share of runs with outcome in original) - (share in arm), in percentage points.
usage: python3 -I boot.py SCRATCH OUT.json"""
import json, sys, collections, random
S, OUT = sys.argv[1], sys.argv[2]
sys.path.insert(0, f"{S}/f1f2/tools")
M3 = ("qwen3_8b", "gptoss_20b", "qwen3_14b"); M2 = ("qwen3_8b", "gptoss_20b")
def both_yes(L, K):
    lab = collections.defaultdict(list)
    for r in "abcd":
        for l in open(f"{L}/ai_{r}.jsonl"):
            x = json.loads(l); lab[x["id"]].append(x["label"])
    return {k["job_id"] for k in json.load(open(K)) if lab[k["id"]].count("yes") == 2 and not k.get("control")}
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
F = {"restr": lambda r: r["n_confirm_requests"] > 0, "auth": lambda r: r["n_executed_unauth"] > 0}
out = {}
rng = random.Random(20261007)
for sname, kinds in SETS.items():
    for kind, (L, K, paths) in kinds.items():
        yes = both_yes(L, K)
        per = collections.defaultdict(lambda: collections.defaultdict(list)); cl = {}
        for p in paths:
            m = p.split("_")[-1].split("/")[0]
            for l in open(p):
                r = json.loads(l)
                if r.get("error") or r.get("run_error") or r["job_id"].startswith("replay-control"): continue
                if r["source_job_id"] in yes:
                    per[r["source_job_id"]][r["arm"]].append(r); cl[r["source_job_id"]] = (r["successor"], r["template_id"])
        f = F[kind]
        arms = sorted({a for v in per.values() for a in v} - {"original"})
        res = {}
        for a in arms:
            d = {k: 100 * (sum(map(f, per[k]["original"])) / len(per[k]["original"]) - sum(map(f, per[k][a])) / len(per[k][a]))
                 for k in per if per[k][a]}
            clusters = collections.defaultdict(list)
            for k, v in d.items(): clusters[cl[k]].append(v)
            cs = list(clusters.values())
            est = sum(d.values()) / len(d)
            bs = []
            for _ in range(4000):
                smp = [rng.choice(cs) for _ in cs]
                vals = [x for c in smp for x in c]
                bs.append(sum(vals) / len(vals))
            bs.sort()
            res[a] = {"est": est, "lo": bs[int(0.025 * len(bs))], "hi": bs[int(0.975 * len(bs)) - 1], "n": len(d), "clusters": len(cs)}
        out[f"{sname}/{kind}"] = res
        print(f"== {sname}/{kind}")
        for a, v in res.items():
            print(f"   {a:15s} {v['est']:6.1f} pp  [{v['lo']:6.1f}, {v['hi']:6.1f}]  sources {v['n']}  clusters {v['clusters']}")
json.dump(out, open(OUT, "w"), indent=1)
