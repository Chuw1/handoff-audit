"""F1 replays the 52 AI-confirmed test sources with the same sampling seeds as the test replay. How often do the
original-arm counts agree? (vLLM sampling with fixed seeds is not fully reproducible.)
usage: python3 -I reproducibility.py DATA_DIR"""
import json, sys, collections
D = sys.argv[1]
def both_yes(L, K):
    lab = collections.defaultdict(list)
    for r in "abcd":
        for l in open(f"{L}/ai_{r}.jsonl"):
            x = json.loads(l); lab[x["id"]].append(x["label"])
    return {k["job_id"] for k in json.load(open(K)) if lab[k["id"]].count("yes") == 2 and not k.get("control")}
L = f"{D}/test310/labels"
R, U = both_yes(L, f"{L}/test_restr_key.json"), both_yes(L, f"{L}/test_auth_key.json")
def orig(paths, keep):
    o = collections.defaultdict(lambda: [0, 0, 0])
    for p in paths:
        for l in open(p):
            r = json.loads(l)
            if r.get("error") or r.get("run_error") or r["arm"] != "original" or r["job_id"].startswith("replay-control"): continue
            if r["source_job_id"] in keep:
                c = o[r["source_job_id"]]; c[0] += r["n_confirm_requests"] > 0; c[1] += r["n_executed_unauth"] > 0; c[2] += 1
    return o
M = ("qwen3_8b", "gptoss_20b")
# the test replay ran restriction and authorization sources in separate jobs; a source can appear in both files
t = orig([f"{D}/test310/raw/runs/test_replay_restr_{m}/replay.jsonl" for m in M], R)
t.update(orig([f"{D}/test310/raw/runs/test_replay_auth_{m}/replay.jsonl" for m in M], U))
f = orig([f"{D}/f1f2/raw/runs/test_replay_f1_{m}/replay.jsonl" for m in M], R | U)
ks = sorted(set(t) & set(f))
print(f"sources in both: {len(ks)} ({len(R)} restriction, {len(U)} authorization)")
print("same original-arm confirmation-request count:", sum(t[k][0] == f[k][0] for k in ks))
print("same confirmation-request and unauthorized-action counts:", sum(t[k][:2] == f[k][:2] for k in ks))
for name, S_, i in (("restriction, runs with a confirmation request", R, 0), ("authorization, runs with an unauthorized action", U, 1)):
    print(f"{name}: test {sum(t[k][i] for k in ks if k in S_)}/{sum(t[k][2] for k in ks if k in S_)}, F1 {sum(f[k][i] for k in ks if k in S_)}/{sum(f[k][2] for k in ks if k in S_)}")
