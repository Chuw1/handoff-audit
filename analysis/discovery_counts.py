"""Discovery counts with the v0.3.10 rule labeler: errors, compaction, flags by type, top templates.
CODE=<stageA> python3 -I disc310.py <trajectories.jsonl> ..."""
import json, os, sys
from collections import Counter
from math import sqrt
sys.path.insert(0, os.environ["CODE"])
from sid.pipeline import relabel_rules
def wilson(k, n, z=1.96):
    if n == 0: return (0, 0)
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)
for path in sys.argv[1:]:
    rows = [json.loads(l) for l in open(path)]
    err = [r for r in rows if r.get("error")]
    ok = [r for r in rows if not r.get("error")]
    comp = [t for t in ok if t.get("compacted")]
    short = [t for t in comp if t["summary"]["n_chars"] < 40]
    ev = [t for t in comp if t["summary"]["n_chars"] >= 40]
    relabel_rules(ev)
    lab = lambda t, k: bool(((t.get("labels_rules") or {}).get("flags") or {}).get(k))
    name = path.split("/")[-2]
    out = [f"{name}: rows {len(rows)}, error {len(err)}, compacted {len(comp)}, <40 chars {len(short)}, analysed {len(ev)}"]
    for k in ("invented_authorization", "invented_restriction", "concealment"):
        n = sum(lab(t, k) for t in ev); lo, hi = wilson(n, len(ev))
        tops = Counter(t["template_id"].split(":")[-1] for t in ev if lab(t, k)).most_common(4)
        out.append(f"   {k:24s} {n}/{len(ev)} = {100*n/max(1,len(ev)):.1f}% [{100*lo:.1f}, {100*hi:.1f}]  templates {len({t['template_id'] for t in ev if lab(t,k)})}  top {tops}")
    if err:
        out.append("   errors: " + str(Counter(str(r['error'])[:90] for r in err).most_common(3)))
    print("\n".join(out))
