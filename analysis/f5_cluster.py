"""F5, post hoc (not in the plan): how the matched-pair result depends on templates, as reported in Appendix H.
Matched pairs = same model, template, seed and run, both summaries readable (as in f5_analysis.py).
Prints the matched shares and their difference, a percentile interval from 4,000 resamples of whole
(model, template) clusters (seed 20261007, as for Figure 4), the exact McNemar test leaving out one template at
a time, and the test without the three report templates.
usage: python3 -I f5_cluster.py RUNS LABELS"""
import json, sys, glob, random, collections
from math import comb
R, L = sys.argv[1], sys.argv[2]
REPORT = ("dev:P3_confidential", "dev:P5_citations", "dev:P8_unverified")
lab = collections.defaultdict(list)
for p in sorted(glob.glob(f"{L}/ai_*.jsonl")):
    for line in open(p):
        x = json.loads(line); lab[x["id"]].append(x["label"])
conf = {x["job_id"] for x in json.load(open(f"{L}/f5_restr_key.json")) if lab[x["id"]].count("yes") == 2}
ep = {}
for a in ("default", "scoped"):
    for m in ("qwen3_8b", "gptoss_20b"):
        for line in open(f"{R}/dev_disc_f5_{a}_{m}/trajectories.jsonl"):
            t = json.loads(line)
            ok = bool(t.get("compacted") and not t.get("error") and t["summary"]["n_chars"] >= 40)
            ep[(a, m, t["template_id"], t["instance_seed"], t["sample"])] = (ok, t["job_id"] in conf)
pairs = []
for k in sorted({k[1:] for k in ep}):
    d, s = ep.get(("default",) + k), ep.get(("scoped",) + k)
    if d and s and d[0] and s[0]:
        pairs.append((k[0], k[1], int(d[1]), int(s[1])))
def mcnemar(ps):
    b = sum(1 for x in ps if x[2] and not x[3]); c = sum(1 for x in ps if x[3] and not x[2]); n = b + c
    p = min(1.0, 2 * sum(comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n) if n else 1.0
    return b, c, p
n = len(pairs); old = sum(x[2] for x in pairs); new = sum(x[3] for x in pairs)
print(f"matched pairs {n}: old prompt {old} ({100 * old / n:.2f}%), new prompt {new} ({100 * new / n:.2f}%), "
      f"difference {100 * (old - new) / n:.2f} points; McNemar {mcnemar(pairs)}")
rep = [x for x in pairs if x[1] in REPORT]
print(f"report templates P3/P5/P8: {sum(x[2] for x in rep)} of the {old} old-prompt and {sum(x[3] for x in rep)} of the "
      f"{new} new-prompt matched restrictions")
cl = collections.defaultdict(list)
for x in pairs:
    cl[(x[0], x[1])].append(x)
keys = sorted(cl); rng = random.Random(20261007); B = 4000; d = []
for _ in range(B):
    smp = [x for k in rng.choices(keys, k=len(keys)) for x in cl[k]]
    d.append(100 * sum(x[2] - x[3] for x in smp) / len(smp))
d.sort()
print(f"cluster bootstrap over {len(keys)} (model, template) clusters, {B} resamples, seed 20261007: "
      f"95% interval {d[int(0.025 * B)]:.1f} to {d[int(0.975 * B) - 1]:.1f} points")
loto = sorted((mcnemar([x for x in pairs if x[1] != tp]) + (tp,) for tp in sorted({x[1] for x in pairs})), key=lambda r: r[2])
print(f"leave one template out: largest p {loto[-1][2]:.3g} (without {loto[-1][3]}: {loto[-1][0]}/{loto[-1][1]})")
print(f"without the three report templates: {mcnemar([x for x in pairs if x[1] not in REPORT])}")
