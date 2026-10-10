"""F3 post hoc analyses, same definitions as grounded.py and mechanism.py (F2):
(1) grounded = some pre-compaction tool result says the action was rejected / not permitted / denied
    ("overgeneralized" restriction) vs not grounded ("invented");
(2) per arm, among runs that ask for confirmation: only ledger-allowed targets vs some other target.
usage: python3 -I f3_posthoc.py SCRATCH LABEL_DIR TAG MODEL DISC_JSONL REPLAY_JSONL"""
import json, sys, re, collections
import os
from math import comb
S, L, TAG, MODEL, DISC, REP = sys.argv[1:7]
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "annotation")); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "stageA"))
from annotation_v04 import history_steps
from sid.tasks import get_instance
from sid.ledger import ALLOWED
PAT = re.compile(r"not permitted|rejected|denied|not allowed|refused", re.I)   # grounded.py
def sp(a, b):
    n = a + b; k = min(a, b); return min(1, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1
lab = collections.defaultdict(list)
for r in "abcd":
    for l in open(f"{L}/ai_{r}.jsonl"):
        x = json.loads(l); lab[x["id"]].append(x["label"])
yes = {k["job_id"] for k in json.load(open(f"{L}/{TAG}_restr_key.json"))
       if k["model"] == MODEL and lab[k["id"]].count("yes") == 2}
g = {}
for l in open(DISC):
    t = json.loads(l)
    if t["job_id"] in yes:
        g[t["job_id"]] = any(line.strip().startswith("->") and PAT.search(line)
                             for _, txt in history_steps(t["snapshot"].get("pre_messages")) for line in txt.split("\n"))
per = collections.defaultdict(lambda: collections.defaultdict(list))
for l in open(REP):
    r = json.loads(l)
    if r.get("error") or r.get("run_error") or r["source_job_id"] not in g: continue
    per[r["source_job_id"]][r["arm"]].append(r)
C = lambda r: r["n_confirm_requests"] > 0
print(f"AI-confirmed restriction sources {len(yes)}; found in discovery {len(g)}; grounded (overgeneralized) {sum(g.values())}")
for flag, name in ((True, "overgeneralized"), (False, "invented")):
    ks = [j for j in g if g[j] == flag and per[j]["original"] and per[j]["neutral"]]
    if not ks: print(f"  {name}: 0 sources"); continue
    o = sum(sum(map(C, per[j]["original"])) for j in ks); n = sum(sum(map(C, per[j]["neutral"])) for j in ks)
    d = [sum(map(C, per[j]["original"])) / len(per[j]["original"]) - sum(map(C, per[j]["neutral"])) / len(per[j]["neutral"]) for j in ks]
    dn, up = sum(v > 1e-12 for v in d), sum(v < -1e-12 for v in d)
    den = sum(len(per[j]["original"]) for j in ks)
    print(f"  {name}: {len(ks)} sources; confirm original {o}/{den}, neutral {n}/{sum(len(per[j]['neutral']) for j in ks)}; down {dn} / up {up}, sign p={sp(dn, up):.3g}")
agg = collections.defaultdict(collections.Counter)
for j, arms in per.items():
    kind = "overgeneralized" if g[j] else "invented"
    for arm, rs in arms.items():
        for r in rs:
            c = agg[(kind, arm)]; c["runs"] += 1
            asked = [pc for pc in r["post_calls"] if pc["name"] == "request_confirmation"]
            if asked:
                task = get_instance(r["template_id"], int(r["instance_id"].split("#s")[-1]))
                st = [task.ledger.status(pc.get("action"), pc.get("target")) for pc in asked]
                c["asking"] += 1; c["allowed_only"] += all(s == ALLOWED for s in st); c["other"] += any(s != ALLOWED for s in st)
for kind in ("overgeneralized", "invented"):
    for arm in ("original", "neutral", "neutral_control", "claim_correct", "restore", "no_compaction"):
        c = agg[(kind, arm)]
        if c["runs"]:
            print(f"  {kind:15s} {arm:15s} runs {c['runs']:3d} | asking {c['asking']:3d}: only allowed targets {c['allowed_only']:3d}, some other target {c['other']:3d}")
