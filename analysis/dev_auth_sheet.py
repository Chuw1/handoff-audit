"""Blind reading sheet for the authorization-flagged source summaries that were replayed (no outcomes)."""
import json, sys, os, random, hashlib, re
sys.path.insert(0, os.environ["CODE"]); sys.path.insert(0, os.environ["ANN"])
from sid.tasks import get_instance
from sid.replay import sentence_spans
import annotation_v04 as A
R = os.environ["RUNS"]
items = []
for m in ["qwen3_8b", "gptoss_20b", "qwen3_14b"]:
    src = {}
    for l in open(f"{R}/replay_v039x_auth_{m}/replay.jsonl"):
        r = json.loads(l)
        if r["job_id"].startswith("replay-control") or r.get("arm") != "original":
            continue
        src[r["source_job_id"]] = (r["targets"], r["target_types"], r.get("claim_pairs"))
    trajs = {}
    for l in open(f"{R}/disc_v039x_{m}/trajectories.jsonl"):
        t = json.loads(l)
        if t["job_id"] in src:
            trajs[t["job_id"]] = t
    assert len(trajs) == len(src), (m, len(trajs), len(src))
    for jid, (tg, ty, cp) in src.items():
        t = trajs[jid]
        it = A.build_item(t, "x")
        items.append({"model": m, "job_id": jid, "targets": tg, "types": ty, "claim_pairs": cp, **it})
rng = random.Random(20261006)
rng.shuffle(items)
key, out = [], []
for i, it in enumerate(items, 1):
    iid = f"U{i:03d}"
    key.append({"id": iid, "model": it["model"], "job_id": it["job_id"], "targets": it["targets"], "types": it["types"]})
    s = [f"=== {iid}", f"REQUEST: {it['request']}", f"RULES:\n{it['rules']}", f"PERMISSION STATE AT COMPACTION:\n{it['permissions']}",
         f"RULE CLAIM PAIRS: {it['claim_pairs']}", "SUMMARY:"]
    for j, x in enumerate(it["sentences"]):
        s.append(f"  {'*' if j in it['targets'] else ' '}S{j+1}: {x}")
    hist = "\n".join(f"  {h[0]}: {h[1]}" for h in it["history"])
    s.append("HISTORY (approval-related lines):")
    for line in hist.split("\n"):
        if re.search(r"approv|confirm|authori|permit|allowed|sign-?off|okay|go ahead|consent", line, re.I):
            s.append("  " + line.strip()[:300])
    out.append("\n".join(s))
open(os.environ["OUT"] + "_sheet.txt", "w").write("\n\n".join(out) + "\n")
json.dump(key, open(os.environ["OUT"] + "_key.json", "w"), indent=1)
print(len(items), "items")
