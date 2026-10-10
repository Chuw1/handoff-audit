"""Blind reading sheets for every replayed test source (flagged + controls). No outcomes are read:
only the original-arm rows' targets/types are used to locate sentences. KIND=auth|restr PREFIX=U|V"""
import json, sys, os, random, re
sys.path.insert(0, os.environ["CODE"]); sys.path.insert(0, os.environ["ANN"])
import annotation_v04 as A
R, KIND, PREFIX, SEED = os.environ["RUNS"], os.environ["KIND"], os.environ["PREFIX"], int(os.environ["SEED"])
items = []
for m in ["qwen3_8b", "gptoss_20b"]:
    src = {}
    for l in open(f"{R}/test_replay_{KIND}_{m}/replay.jsonl"):
        r = json.loads(l)
        if r.get("arm") != "original" or r.get("error"):
            continue
        ctl = r["job_id"].startswith("replay-control")
        src[r["source_job_id"]] = (r["targets"], r.get("target_types") or [], r.get("claim_pairs"), ctl)
    trajs = {}
    for l in open(f"{R}/test_disc_v0310_{m}/trajectories.jsonl"):
        t = json.loads(l)
        if t["job_id"] in src:
            trajs[t["job_id"]] = t
    assert len(trajs) == len(src), (m, len(trajs), len(src))
    for jid, (tg, ty, cp, ctl) in src.items():
        it = A.build_item(trajs[jid], "x")
        items.append({"model": m, "job_id": jid, "targets": tg, "types": ty, "claim_pairs": cp, "control": ctl, **it})
rng = random.Random(SEED)
rng.shuffle(items)
key, out = [], []
for i, it in enumerate(items, 1):
    iid = f"{PREFIX}{i:03d}"
    key.append({"id": iid, "model": it["model"], "job_id": it["job_id"], "targets": it["targets"],
                "types": it["types"], "control": it["control"]})
    s = [f"=== {iid}", f"REQUEST: {it['request']}", f"RULES:\n{it['rules']}",
         f"PERMISSION STATE AT COMPACTION:\n{it['permissions']}",
         f"RULE CLAIM PAIRS: {it['claim_pairs'] if not it['control'] else []}", "SUMMARY:"]
    for j, x in enumerate(it["sentences"]):
        s.append(f"  {'*' if (j in it['targets'] and not it['control']) else ' '}S{j+1}: {x}")
    s.append("HISTORY (approval-related lines):")
    for h in it["history"]:
        for line in f"{h[0]}: {h[1]}".split("\n"):
            if re.search(r"approv|confirm|authori|permit|allowed|sign-?off|okay|go ahead|consent", line, re.I):
                s.append("  " + line.strip()[:300])
    out.append("\n".join(s))
open(os.environ["OUT"] + "_sheet.txt", "w").write("\n\n".join(out) + "\n")
json.dump(key, open(os.environ["OUT"] + "_key.json", "w"), indent=1)
print(KIND, len(items), "items;", sum(k["control"] for k in key), "controls")
