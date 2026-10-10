"""Monitor comparison over four views (cot / summary / actions / all).

Scores every trajectory in each view with the same monitor model, sets the
threshold per view on the calibration set at --fpr, and reports recall,
precision and FPR on the evaluation set. With only dev data, the dev
templates are split in half by template (calibration vs evaluation); this is
exploratory and must be labeled as such.

  python scripts/run_monitor_eval.py --model vllm:<monitor>@<url> \
      --from runs/disc_qwen3_8b/trajectories.jsonl --out runs/mon_qwen3_8b --target directive
"""
import argparse
import json
import os
import random

import _path  # noqa: F401
from sid.monitor import VIEWS, calibrate_and_evaluate
from sid.pipeline import monitor_fn, relabel_rules, traj_label
from sid.runner import common_args, factory_from_args, read_jsonl, run_jobs, spec_id, write_manifest


def main():
    p = common_args(argparse.ArgumentParser(description=__doc__))
    p.add_argument("--from", dest="src", nargs="+", required=True)
    p.add_argument("--target", default="directive", choices=["directive", "violation"])
    p.add_argument("--label-source", default="rules", choices=["rules", "judge"])
    p.add_argument("--fpr", type=float, default=0.05)
    p.add_argument("--views", nargs="*", default=list(VIEWS))
    p.add_argument("--stored-labels", action="store_true",
                   help="use the rule labels stored at run time (v0.3.10 default: recompute them with the current "
                        "labeler, as run_replay.py and analyze.py do)")
    args = p.parse_args()
    trajs = [t for f in args.src for t in read_jsonl(f) if t.get("compacted") and not t.get("error")]
    if args.label_source == "rules" and not args.stored_labels:
        print(f"rule labels recomputed with the current labeler for {relabel_rules(trajs)} trajectories")
    write_manifest(args.out, args, {"stage": "monitor", "n_traj": len(trajs)})
    jobs = []
    for t in trajs:
        for v in args.views:
            jobs.append({"job_id": f"mon|{spec_id(args.model)}|{v}|{t['job_id']}", "traj": t, "view": v,
                         "label_directive": traj_label(t, "directive", args.label_source),
                         "label_violation": traj_label(t, "violation")})
    out = os.path.join(args.out, "monitor_scores.jsonl")
    run_jobs(jobs, monitor_fn(factory_from_args(args), args.model), out, args.workers, "monitor")
    rows = [r for r in read_jsonl(out) if not r.get("error")]
    key = "label_directive" if args.target == "directive" else "label_violation"
    for r in rows:
        r["label"] = bool(r[key])
    dev = [r for r in rows if r["split"] == "dev"]
    test = [r for r in rows if r["split"] == "test"]
    note = "calibrated on dev, evaluated on test"
    if not test:
        tids = sorted({r["template_id"] for r in dev})
        random.Random(0).shuffle(tids)
        cal = set(tids[: len(tids) // 2])
        test = [r for r in dev if r["template_id"] not in cal]
        dev = [r for r in dev if r["template_id"] in cal]
        note = "EXPLORATORY: dev templates split in half (calibration / evaluation)"
    rep = {"note": note, "target": args.target, "fpr_target": args.fpr,
           "n_cal": len(dev) // max(1, len(args.views)), "n_eval": len(test) // max(1, len(args.views)),
           "positives_eval": sum(r["label"] for r in test) // max(1, len(args.views)),
           "views": calibrate_and_evaluate(dev, test, args.fpr)}
    with open(os.path.join(args.out, f"monitor_report_{args.target}.json"), "w") as f:
        json.dump(rep, f, indent=1)
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
