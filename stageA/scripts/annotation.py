"""Human annotation for validating the labelers.

  # 1. export blinded sheets (stratified: all flagged + an equal number of unflagged summaries)
  python scripts/annotation.py export --from runs/disc_qwen3_8b/trajectories.jsonl --n 100 --out ann/batch1
  # 2. two people fill the `label` column independently (allowed labels in ann/batch1_LABELS.txt)
  # 3. agreement: human vs human, and each human vs rule labels / judge labels
  python scripts/annotation.py agree --from runs/disc_qwen3_8b/trajectories.jsonl \
      --sheets ann/batch1_annotator1.csv ann/batch1_annotator2.csv

The item_id is a hash, so annotators cannot see model, arm, or automatic label.
"""
import argparse
import hashlib
import json
import os
import random

import _path  # noqa: F401
from sid.label.annotate import agreement, export_sheet, read_sheet
from sid.ledger import EventLog
from sid.replay import sentences
from sid.runner import read_jsonl

RULE_TO_LABEL = {"invented_authorization": "invented_authorization",
                 "invented_restriction": "invented_restriction", "concealment": "concealment",
                 "persona": "persona", "misattributed_source": "misattributed_source"}


def item_id(t):
    return hashlib.sha256(t["job_id"].encode()).hexdigest()[:10]


def auto_labels(trajs):
    rules, judge = {}, {}
    for t in trajs:
        iid = item_id(t)
        n = len(sentences(t["summary"]["text"]))
        for i in range(n):
            rules[(iid, i)] = "faithful"
        for c in (t.get("labels_rules") or {}).get("candidates", []):
            if not c["supported"] and c["type"] in RULE_TO_LABEL:
                rules[(iid, c["sentence_idx"])] = RULE_TO_LABEL[c["type"]]
        for s in (t.get("labels_judge") or {}).get("sentences", []):
            judge[(iid, s["i"])] = s["label"]
    return rules, judge


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--from", dest="src", nargs="+", required=True)
    e.add_argument("--n", type=int, default=100)
    e.add_argument("--out", required=True)
    a = sub.add_parser("agree")
    a.add_argument("--from", dest="src", nargs="+", required=True)
    a.add_argument("--sheets", nargs="+", required=True)
    args = ap.parse_args()
    trajs = [t for f in args.src for t in read_jsonl(f) if t.get("compacted") and not t.get("error")]
    if args.cmd == "export":
        flagged = [t for t in trajs if (t.get("labels_rules") or {}).get("any_counted")
                   or (t.get("labels_judge") or {}).get("any_counted")]
        other = [t for t in trajs if t not in flagged]
        rng = random.Random(0)
        k = min(len(flagged), args.n // 2)
        pick = rng.sample(flagged, k) + rng.sample(other, min(len(other), args.n - k))
        items = []
        for t in pick:
            ev = EventLog.from_list(t["snapshot"]["env"]["events"]).events
            items.append({"item_id": item_id(t), "summary": t["summary"]["text"],
                          "user_request": t.get("user_prompt", ""),
                          "task_rules": " | ".join(t.get("rules", [])),
                          "approval_events": "; ".join(f"step {x.step}: {x.kind} {x.action} {x.target}"
                                                       for x in ev) or "none"})
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        paths = export_sheet(items, args.out)
        with open(args.out + "_key.json", "w") as f:   # keep away from annotators
            json.dump({item_id(t): t["job_id"] for t in pick}, f, indent=1)
        print("wrote", paths, f"({len(pick)} summaries, {k} flagged by an automatic labeler)")
    else:
        sheets = {os.path.basename(p): read_sheet(p) for p in args.sheets}
        rules, judge = auto_labels(trajs)
        auto = {"rules": rules}
        if judge:
            auto["judge"] = judge
        print(json.dumps(agreement(sheets, auto), indent=1))


if __name__ == "__main__":
    main()
