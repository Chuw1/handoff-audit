"""F4 numbers reported in Appendix G that f4_primary.py does not print: readable summaries by compaction
point, prevalence of AI-confirmed unsupported policy among summaries written at the fixed step (Wilson 95%),
what the tied primary sources look like, the full-history authorization case, and the time between the
label hashes and the first F4 replay.
usage: python3 -I f4_extra.py DATA_DIR   (uses f4/raw/runs, f4/labels, f4/targets, f4r2/raw/runs)"""
import json, sys, math, collections, datetime, glob
D = sys.argv[1]
MOD = ("qwen3_8b", "gptoss_20b")

def wilson(x, n, z=1.959963984540054):
    p = x / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return 100 * p, 100 * (c - h), 100 * (c + h)

lab = collections.defaultdict(list)
for r in "abcd":
    for l in open(f"{D}/f4/labels/ai_{r}.jsonl"):
        x = json.loads(l); lab[x["id"]].append(x["label"])
conf = {}  # job_id -> 'restr' / 'auth'
for k in ("auth", "restr"):
    for x in json.load(open(f"{D}/f4/labels/f4_{k}_key.json")):
        if lab[x["id"]].count("yes") == 2:
            conf[x["job_id"]] = k

print("== readable summaries and AI-confirmed sources, by compaction point")
for m in MOD:
    ts = [json.loads(l) for l in open(f"{D}/f4/raw/runs/test_disc_f4_{m}/trajectories.jsonl")]
    comp = [t for t in ts if t.get("compacted")]
    read = [t for t in comp if not t.get("error") and t["summary"]["n_chars"] >= 40]
    by = collections.Counter(t.get("compaction_reason") for t in read)
    cr = collections.Counter((conf[t["job_id"]], t.get("compaction_reason")) for t in read if t["job_id"] in conf)
    print(f"{m}: episodes {len(ts)}, compacted {len(comp)}, readable {len(read)} {dict(sorted(by.items()))}")
    print(f"   AI-confirmed sources by (kind, compaction point): {dict(sorted(cr.items()))}")
    n = by["step"]
    for k in ("restr", "auth"):
        x = cr[(k, "step")]; p, lo, hi = wilson(x, n)
        print(f"   {k} among step-compacted readable summaries: {x}/{n} = {p:.1f}% (Wilson 95% {lo:.1f}-{hi:.1f}%)")

per = collections.defaultdict(lambda: collections.defaultdict(list)); kind = {}
for m in MOD:
    tg = json.load(open(f"{D}/f4/targets/targets_f4_{m}.json"))
    for k, v in tg.items():
        kind[k] = (m, v["types"])
    for l in open(f"{D}/f4r2/raw/runs/test_replay_f4_{m}/replay.jsonl"):
        r = json.loads(l)
        if r.get("error") or r.get("run_error"):
            continue
        per[r["source_job_id"]][r["arm"]].append(r)

print("== primary sample: sources whose rate did not change (original vs neutral)")
ties = collections.Counter()
for k, (m, types) in kind.items():
    if "invented_restriction" not in types:
        continue
    o = sum(r["n_confirm_requests"] > 0 for r in per[k]["original"])
    n_ = sum(r["n_confirm_requests"] > 0 for r in per[k]["neutral"])
    if o == n_:
        ties[f"{o}/4 in both arms"] += 1
print(f"   tied sources {sum(ties.values())}: {dict(sorted(ties.items()))}")

print("== authorization sources with an unauthorized action under the full history")
for k, (m, types) in sorted(kind.items()):
    if "invented_authorization" not in types:
        continue
    full = sum(r["n_executed_unauth"] > 0 for r in per[k]["no_compaction"])
    if full:
        arms = {a: sum(r["n_executed_unauth"] > 0 for r in rs) for a, rs in sorted(per[k].items())}
        print(f"   {m} {k.split('|')[-3]}: {arms}")

print("== label hashes vs first F4 replay")
frozen = [l for l in open(f"{D}/f4r2/raw/F4_AI_LABELS_SHA256.txt") if l.startswith("frozen:")][0]
txt = frozen.split("frozen:")[1].strip()
for fmt in ("%a %b %d %H:%M:%S UTC %Y", "%a %b %d %I:%M:%S %p UTC %Y"):
    try:
        t_lab = datetime.datetime.strptime(" ".join(txt.split()), fmt).replace(tzinfo=datetime.timezone.utc); break
    except ValueError:
        continue
starts = []
for p in sorted(glob.glob(f"{D}/f4r2/raw/runs/test_replay_f4_*/manifest_*.json")):
    starts.append(datetime.datetime.strptime(json.load(open(p))["time"], "%Y-%m-%dT%H:%M:%S%z"))
first = min(starts)
print(f"   labels hashed {t_lab.isoformat()}; first replay started {first.astimezone(datetime.timezone.utc).isoformat()}; "
      f"gap {(first - t_lab).total_seconds() / 60:.1f} minutes")

print("== cluster bootstrap of the mean per-source drop (method of boot.py: whole (model, template) clusters,")
print("   4,000 resamples, percentile interval, seed 20261007; descriptive, the plan's test is the sign test)")
import random
for kname, typ, f in (("restriction, confirmation requests", "invented_restriction", lambda r: r["n_confirm_requests"] > 0),
                      ("authorization, unauthorized actions", "invented_authorization", lambda r: r["n_executed_unauth"] > 0)):
    d, cl = {}, {}
    for k, (m, types) in kind.items():
        if typ not in types:
            continue
        o = per[k]["original"]; a = per[k]["neutral"]
        d[k] = 100 * (sum(map(f, o)) / len(o) - sum(map(f, a)) / len(a))
        cl[k] = (o[0]["successor"], o[0]["template_id"])
    groups = collections.defaultdict(list)
    for k, v in d.items():
        groups[cl[k]].append(v)
    cs = list(groups.values()); rng = random.Random(20261007); bs = []
    for _ in range(4000):
        vals = [x for c in (rng.choice(cs) for _ in cs) for x in c]
        bs.append(sum(vals) / len(vals))
    bs.sort()
    print(f"   {kname}: sources {len(d)}, clusters {len(cs)}, mean drop {sum(d.values()) / len(d):.1f} pp, "
          f"95% interval {bs[100]:.1f} to {bs[3899]:.1f} pp")
