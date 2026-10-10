"""Post hoc checks after the F2 primary: per-source table, leave-one-cell-out, F1+F2 pooled, prevalence.
usage: python3 -I f2_extra.py SCRATCH"""
import json, sys, collections, math
from math import comb
S = sys.argv[1]
def sp(a, b):
    n = a + b; k = min(a, b); return min(1, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1
def load(R, TD, tag):
    per = collections.defaultdict(lambda: collections.defaultdict(list)); info = {}
    for m in ["qwen3_8b", "gptoss_20b"]:
        tf = json.load(open(f"{TD}/targets_{tag}_{m}.json"))
        for l in open(f"{R}/test_replay_{tag}_{m}/replay.jsonl"):
            r = json.loads(l); k = (tag, m, r["source_job_id"]); per[k][r["arm"]].append(r)
            info[k] = (tf[r["source_job_id"]]["types"][0], r["template_id"].split(":")[-1], tf[r["source_job_id"]].get("items"))
    return per, info
p1, i1 = load(f"{S}/f1f2/raw/runs", f"{S}/f1f2/raw", "f1")
p2, i2 = load(f"{S}/f2r2/raw/runs", f"{S}/f2r2/raw", "f2")
C = lambda r: r["n_confirm_requests"] > 0; E = lambda r: r["n_executed_unauth"] > 0
cnt = lambda per, k, a, f: sum(map(f, per[k][a]))
print("F2 restriction per source, confirmation requests out of 4:")
for k in sorted(p2, key=lambda k: (k[1], i2[k][1])):
    if i2[k][0] != "invented_restriction": continue
    print(f"  {k[1]:10s} {i2[k][1]:28s} {i2[k][2]} orig {cnt(p2,k,'original',C)} neu {cnt(p2,k,'neutral',C)} "
          f"nc {cnt(p2,k,'neutral_control',C)} del {cnt(p2,k,'delete',C)}")
keys = [k for k in p2 if i2[k][0] == "invented_restriction"]
print("leave-one-(model,template)-cell-out, F2 restriction, original vs neutral:")
for c in sorted(set((k[1], i2[k][1]) for k in keys)):
    d = [cnt(p2, k, 'original', C) - cnt(p2, k, 'neutral', C) for k in keys if (k[1], i2[k][1]) != c]
    a = sum(x > 0 for x in d); b = sum(x < 0 for x in d)
    print(f"   drop {c}: down {a} up {b} p={sp(a,b):.3f}")
print("F1+F2 pooled (both edit every marked sentence; post hoc):")
for typ, f, nm in (("invented_restriction", C, "restr confirm"), ("invented_authorization", E, "auth exec"), ("invented_authorization", C, "auth confirm")):
    for arm in ("neutral", "neutral_control", "delete", "no_compaction"):
        a = b = no = nn = den = 0
        for per, info in ((p1, i1), (p2, i2)):
            for k in per:
                if info[k][0] != typ: continue
                d = cnt(per, k, 'original', f) - cnt(per, k, arm, f); a += d > 0; b += d < 0
                no += cnt(per, k, 'original', f); nn += cnt(per, k, arm, f); den += len(per[k]['original'])
        print(f"   {nm:13s} {arm:15s} original {no}/{den} -> {nn}/{den}  down {a} up {b} p={sp(a,b):.4f}")
print("prevalence in F2 discovery (AI-confirmed / summaries eligible for reading), Wilson 95%:")
def wil(k, n, z=1.96):
    p = k / n; c = (p + z * z / (2 * n)) / (1 + z * z / n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return f"{100*(c-h):.1f}-{100*(c+h):.1f}%"
for m in ["qwen3_8b", "gptoss_20b"]:
    n = sum(1 for l in open(f"{S}/f1f2/raw/runs/test_disc_f2_{m}/trajectories.jsonl")
            for t in [json.loads(l)] if t.get("compacted") and not t.get("error") and t["summary"]["n_chars"] >= 40)
    rk = sum(1 for k in p2 if k[1] == m and i2[k][0] == "invented_restriction")
    ak = sum(1 for k in p2 if k[1] == m and i2[k][0] == "invented_authorization")
    print(f"   {m}: eligible {n}; restriction {rk} ({100*rk/n:.1f}%, {wil(rk,n)}); authorization {ak} ({100*ak/n:.1f}%, {wil(ak,n)})")
