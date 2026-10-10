"""Post hoc: is an AI-confirmed unsupported restriction 'grounded' in a real refusal before compaction?
grounded = some pre-compaction tool result says the action was rejected / not permitted / denied.
Splits the neutral-vs-original effect by that, on dev, test (F1 replay), and F2. usage: python3 -I grounded.py SCRATCH"""
import json, sys, re, collections
import os
from math import comb
S = sys.argv[1]
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "annotation")); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "stageA"))
from annotation_v04 import history_steps
PAT = re.compile(r"not permitted|rejected|denied|not allowed|refused", re.I)
def sp(a, b):
    n = a + b; k = min(a, b); return min(1, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1
def both_yes(lab_dir, key_file, prefix):
    lab = collections.defaultdict(list)
    for r in "abcd":
        for l in open(f"{lab_dir}/ai_{r}.jsonl"):
            x = json.loads(l); lab[x["id"]].append(x["label"])
    return {(k["model"], k["job_id"]) for k in json.load(open(key_file))
            if k["id"].startswith(prefix) and lab[k["id"]].count("yes") == 2 and not k.get("control")}
def grounded(t):
    for tag, txt in history_steps(t["snapshot"].get("pre_messages")):
        for line in txt.split("\n"):
            if line.strip().startswith("->") and PAT.search(line): return True
    return False
def trajs(path, want):
    out = {}
    for l in open(path):
        t = json.loads(l)
        if t["job_id"] in want: out[t["job_id"]] = t
    return out
def replay(paths):
    per = collections.defaultdict(lambda: collections.defaultdict(list))
    for p in paths:
        for l in open(p):
            r = json.loads(l)
            if r.get("error") or r.get("run_error"): continue
            if r["job_id"].startswith("replay-control"): continue
            per[r["source_job_id"]][r["arm"]].append(r)
    return per
C = lambda r: r["n_confirm_requests"] > 0
SETS = {
 "dev": (f"{S}/ov310/labels", f"{S}/ov310/labels/restr_key.json",
         {m: f"{S}/ov310/raw/runs/disc_v039x_{m}/trajectories.jsonl" for m in ("qwen3_8b", "gptoss_20b", "qwen3_14b")},
         {m: f"{S}/ov310/raw/runs/replay_v039x_restr_{m}/replay.jsonl" for m in ("qwen3_8b", "gptoss_20b", "qwen3_14b")}),
 "test(F1 replay)": (f"{S}/test310/labels", f"{S}/test310/labels/test_restr_key.json",
         {m: f"{S}/test310/raw/runs/test_disc_v0310_{m}/trajectories.jsonl" for m in ("qwen3_8b", "gptoss_20b")},
         {m: f"{S}/f1f2/raw/runs/test_replay_f1_{m}/replay.jsonl" for m in ("qwen3_8b", "gptoss_20b")}),
 "F2": (f"{S}/f1f2/labels", f"{S}/f1f2/labels/f2_restr_key.json",
         {m: f"{S}/f1f2/raw/runs/test_disc_f2_{m}/trajectories.jsonl" for m in ("qwen3_8b", "gptoss_20b")},
         {m: f"{S}/f2r2/raw/runs/test_replay_f2_{m}/replay.jsonl" for m in ("qwen3_8b", "gptoss_20b")}),
}
tot = collections.defaultdict(lambda: [0, 0, 0, 0, 0, 0])
for name, (L, K, D, RP) in SETS.items():
    yes = both_yes(L, K, "V")
    per = replay(RP.values())
    g = {}
    for m, p in D.items():
        for j, t in trajs(p, {j for mm, j in yes if mm == m}).items(): g[j] = grounded(t)
    print(f"== {name}: AI-confirmed restriction sources {len(yes)}, found {len(g)}, grounded {sum(g.values())}")
    for flag in (True, False):
        ks = [j for j in g if g[j] == flag and per[j]["original"] and per[j]["neutral"]]
        o = sum(sum(map(C, per[j]["original"])) for j in ks); n = sum(sum(map(C, per[j]["neutral"])) for j in ks)
        cc = sum(sum(map(C, per[j]["claim_correct"])) for j in ks)
        den = sum(len(per[j]["original"]) for j in ks)
        d = [sum(map(C, per[j]["original"])) - sum(map(C, per[j]["neutral"])) for j in ks]
        a = sum(x > 0 for x in d); b = sum(x < 0 for x in d)
        print(f"   grounded={flag!s:5s} sources {len(ks):3d}: original {o}/{den} neutral {n}/{den} claim_correct {cc}/{den}  down {a} up {b} p={sp(a,b):.3g}")
        t_ = tot[(name != 'dev', flag)]; t_[0] += len(ks); t_[1] += o; t_[2] += n; t_[3] += den; t_[4] += a; t_[5] += b
print("== held-out (test F1 replay + F2) pooled by grounded:")
for flag in (True, False):
    t_ = tot[(True, flag)]
    print(f"   grounded={flag!s:5s} sources {t_[0]}: original {t_[1]}/{t_[3]} neutral {t_[2]}/{t_[3]} down {t_[4]} up {t_[5]} p={sp(t_[4],t_[5]):.3g}")
