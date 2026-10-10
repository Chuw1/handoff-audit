import json, sys, collections
S = sys.argv[1]
def kappa(pairs):
    cats = sorted({c for p in pairs for c in p}); n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    ca = collections.Counter(a for a, _ in pairs); cb = collections.Counter(b for _, b in pairs)
    pe = sum(ca[c] * cb[c] for c in cats) / n / n
    return (po - pe) / (1 - pe) if pe < 1 else float('nan'), po, n, collections.Counter(pairs)
def labs(r):
    return {json.loads(l)["id"]: json.loads(l) for l in open(f"{S}/h3/labels/ai_{r}.jsonl")}
L = {r: labs(r) for r in "abcd"}
traj = {}
elig = collections.Counter(); flags = collections.Counter()
for p in ("h3s", "h3b"):
    for m in ("qwen3_8b", "gptoss_20b"):
        n = 0
        for l in open(f"{S}/ov310/raw/runs/disc_{p}_{m}/trajectories.jsonl"):
            x = json.loads(l)
            traj[x["job_id"]] = x
            if x.get("error") or not x.get("compacted"): continue
            s = x.get("summary") or {}
            if (s.get("n_chars") or 0) < 40: continue
            elig[(p, m)] += 1
            fl = (x.get("labels_rules") or {}).get("flags", {})
            for k in ("invented_restriction", "invented_authorization"):
                flags[(p, m, k)] += bool(fl.get(k))
print("eligible", dict(elig)); print("flags", dict(flags))
for p, (r1, r2) in (("h3s", "ab"), ("h3b", "cd")):
    for kind in ("restr", "auth"):
        key = json.load(open(f"{S}/h3/labels/{p}_{kind}_key.json"))
        conf = collections.Counter(); pairs = []; missing = 0; inel = 0; notflag = 0
        for k in key:
            a, b = L[r1].get(k["id"]), L[r2].get(k["id"])
            if a is None or b is None: missing += 1; continue
            pairs.append((a["label"], b["label"]))
            x = traj.get(k["job_id"])
            if x is None: inel += 1; continue
            fl = x["labels_rules"]["flags"]["invented_restriction" if kind == "restr" else "invented_authorization"]
            notflag += not fl
            if a["label"] == "yes" and b["label"] == "yes": conf[k["model"]] += 1
        kp = kappa(pairs)
        print(f"{p} {kind}: items {len(key)} missing {missing} notintraj {inel} notflagged {notflag} confirmed {dict(conf)} kappa {kp[0]:.3f} agree {kp[1]:.3f} n {kp[2]} {dict(kp[3])}")
# ensure ids in label files correspond to the right sheet
for r in "abcd": print(r, len(L[r]))
