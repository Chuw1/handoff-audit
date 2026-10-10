"""Prevalence in the scale checks: AI-confirmed unsupported restrictions and authorizations over the summaries
eligible for reading (compacted, no error, summary of at least 40 characters), with Wilson 95% intervals, and
the share of compactions at the finish call. usage: python3 -I scale_prevalence.py DATA_DIR"""
import json, sys, math, collections
D = sys.argv[1]
def wil(k, n, z=1.96):
    p = k / n; c = (p + z * z / (2 * n)) / (1 + z * z / n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return f"{100 * (c - h):.1f}-{100 * (c + h):.1f}%"
def confirmed(L, K):
    lab = collections.defaultdict(list)
    for r in "abcd":
        for l in open(f"{L}/ai_{r}.jsonl"):
            x = json.loads(l); lab[x["id"]].append(x["label"])
    return {k["job_id"] for k in json.load(open(K)) if lab[k["id"]].count("yes") == 2 and not k.get("control")}
for name, tag, disc in (("gpt-oss-120b", "f3", "f3/raw/runs/test_disc_f3_gptoss_120b"), ("Qwen3-235B-A22B-FP8", "f3c", "f3c/raw/runs/test_disc_f3c_qwen3_235b")):
    ts = [json.loads(l) for l in open(f"{D}/{disc}/trajectories.jsonl")]
    el = [t for t in ts if t.get("compacted") and not t.get("error") and t["summary"]["n_chars"] >= 40]
    ids = {t["job_id"] for t in el}
    r = len(confirmed(f"{D}/{tag}/labels", f"{D}/{tag}/labels/{tag}_restr_key.json") & ids)
    a = len(confirmed(f"{D}/{tag}/labels", f"{D}/{tag}/labels/{tag}_auth_key.json") & ids)
    fin = sum(t.get("compaction_reason") == "before_finish" for t in el)
    n = len(el)
    print(f"{name}: episodes {len(ts)}, eligible {n}; restriction {r} ({100 * r / n:.1f}%, {wil(r, n)}); "
          f"authorization {a} ({100 * a / n:.1f}%, {wil(a, n)}); compacted at finish {fin} ({100 * fin / n:.0f}%)")
