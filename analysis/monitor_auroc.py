import json, sys, collections
for p in sys.argv[1:]:
    by = collections.defaultdict(list); bad = 0; n = 0
    for l in open(p):
        r = json.loads(l); n += 1
        if not r.get("parse_ok") or r.get("error") or r.get("score") is None: bad += 1; continue
        by[r["view"]].append((r["score"], bool(r["label_directive"])))
    print(p.split("/")[-2], "rows", n, "bad", bad, f"{bad/n:.3f}")
    for v, xs in sorted(by.items()):
        pos = [s for s, y in xs if y]; neg = [s for s, y in xs if not y]
        a = sum((sp > sn) + 0.5 * (sp == sn) for sp in pos for sn in neg) / (len(pos) * len(neg))
        print(f"   {v:8s} n={len(xs)} pos={len(pos)} AUROC={a:.5f}")
