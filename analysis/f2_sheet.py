"""F2: blind reading sheets for every rule-flagged (restriction / authorization) summary in the fresh discovery
runs. Reads discovery files only (no replay exists yet). RUNS=<dir with test_disc_f2_<m>> OUT=<prefix>"""
import json, sys, os, random, re
sys.path.insert(0, os.environ["CODE"]); sys.path.insert(0, os.environ["ANN"])
import annotation_v04 as A
from sid.pipeline import relabel_rules
R, OUT = os.environ["RUNS"], os.environ["OUT"]
DISC = os.environ.get("DISC", "test_disc_f2_{m}")
for kind, typ, prefix, seed in (("auth", "invented_authorization", "U", 20261011), ("restr", "invented_restriction", "V", 20261012)):
    items = []
    for m in ("qwen3_8b", "gptoss_20b"):
        ts = [json.loads(l) for l in open(f"{R}/{DISC.format(m=m)}/trajectories.jsonl")]
        ts = [t for t in ts if t.get("compacted") and not t.get("error") and t["summary"]["n_chars"] >= 40]
        relabel_rules(ts)
        for t in ts:
            lab = t["labels_rules"]
            tg = sorted({c["sentence_idx"] for c in lab.get("counted", []) if (c.get("type") or c.get("label")) == typ})
            if not tg:
                continue
            it = A.build_item(t, "x")
            items.append({"model": m, "job_id": t["job_id"], "targets": tg, **it})
    random.Random(seed).shuffle(items)
    key, out = [], []
    for i, it in enumerate(items, 1):
        iid = f"{prefix}{i:03d}"
        key.append({"id": iid, "model": it["model"], "job_id": it["job_id"], "targets": it["targets"], "types": [typ]})
        s = [f"=== {iid}", f"REQUEST: {it['request']}", f"RULES:\n{it['rules']}",
             f"PERMISSION STATE AT COMPACTION:\n{it['permissions']}", "SUMMARY:"]
        for j, x in enumerate(it["sentences"]):
            s.append(f"  {'*' if j in it['targets'] else ' '}S{j+1}: {x}")
        s.append("HISTORY (approval-related lines):")
        for h in it["history"]:
            for line in f"{h[0]}: {h[1]}".split("\n"):
                if re.search(r"approv|confirm|authori|permit|allowed|sign-?off|okay|go ahead|consent", line, re.I):
                    s.append("  " + line.strip()[:300])
        out.append("\n".join(s))
    open(f"{OUT}_{kind}_sheet.txt", "w").write("\n\n".join(out) + "\n")
    json.dump(key, open(f"{OUT}_{kind}_key.json", "w"), indent=1)
    print(kind, len(items), "items", {m: sum(k["model"] == m for k in key) for m in ("qwen3_8b", "gptoss_20b")})
