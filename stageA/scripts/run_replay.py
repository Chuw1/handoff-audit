"""Arms 3-5: paired replay of flagged summaries (and cross-model hand-off).

Reads discovery trajectories, keeps those whose summary has a counted
directive (rule labels by default, --label-source judge for judge labels),
and replays the successor under original / delete / neutral / restore /
edit_control (+ no_compaction) with paired seeds. --successor runs the same
arms with a different successor model (cross-model hand-off).
--control-n also replays that many unflagged trajectories (original vs
edit_control vs no_compaction) as a baseline for edit effects.

  python scripts/run_replay.py --model vllm:Qwen/Qwen3-8B@http://localhost:8000/v1 \
      --from runs/disc_qwen3_8b/trajectories.jsonl --replays 8 --out runs/replay_qwen3_8b
"""
import argparse
import os
import random

import _path  # noqa: F401
from sid.pipeline import cfg_from_args, relabel_rules, replay_fn, replay_targets
from sid.replay import ARMS_VERSION, DEFAULT_ARMS, sentences
from sid.runner import common_args, factory_from_args, read_jsonl, run_jobs, settings_tag, spec_id, write_manifest


def main():
    p = common_args(argparse.ArgumentParser(description=__doc__))
    p.add_argument("--from", dest="src", required=True, help="discovery trajectories.jsonl")
    p.add_argument("--label-source", default="rules", choices=["rules", "judge"])
    p.add_argument("--replays", type=int, default=8)
    p.add_argument("--no-baseline", action="store_true", help="skip the no_compaction arm")
    p.add_argument("--control-n", type=int, default=0, help="unflagged trajectories to replay as controls")
    p.add_argument("--max-flagged", type=int, default=0, help="cap on flagged trajectories (0 = all)")
    p.add_argument("--arms", nargs="*", default=list(DEFAULT_ARMS),
                   choices=list(DEFAULT_ARMS) + ["correct", "pressure", "neutral_control"],   # v0.3.9: a typo is an error, not a lost arm
                   help="add 'pressure' for the urgency control")
    p.add_argument("--stored-labels", action="store_true",
                   help="select by the rule labels stored at run time (v0.3.4 default: recompute them with the "
                        "current labeler first)")
    p.add_argument("--skip-templates", nargs="*", default=[],
                   help="template id suffixes to leave out, e.g. runs hit by a fixed harness bug")
    p.add_argument("--types", nargs="*", default=None, choices=["authorization", "restriction", "concealment"],
                   help="v0.3.10: replay only summaries flagged for these counted types (default: all flagged); "
                        "--max-flagged then caps the selected ones")
    p.add_argument("--targets-file", default=None,
                   help="v0.3.10.1: JSON {source job_id: {\"targets\": [0-based sentence indices], \"types\": [...]}}; "
                        "replays exactly these summaries with these sentences edited (labels fixed before the run) "
                        "instead of the rule labeler's targets; --types/--max-flagged/--control-n do not apply")
    args = p.parse_args()
    trajs = [t for t in read_jsonl(args.src) if t.get("compacted") and not t.get("error")]
    if args.templates:
        trajs = [t for t in trajs if t["template_id"].split(":")[-1] in args.templates]
    if args.skip_templates:
        trajs = [t for t in trajs if t["template_id"].split(":")[-1] not in args.skip_templates]
    if args.label_source == "rules" and not args.stored_labels:
        print(f"rule labels recomputed with the current labeler for {relabel_rules(trajs)} trajectories")
    succ_spec = args.successor or args.model
    tag = f"{','.join(args.arms)}|arms_v={ARMS_VERSION}|K={args.replays}|nc={int(not args.no_baseline)}|{settings_tag(args)}"
    if args.targets_file:
        import hashlib
        import json
        raw = open(args.targets_file, "rb").read()
        want = json.loads(raw)
        tf = hashlib.sha256(raw).hexdigest()
        by_id = {t["job_id"]: t for t in trajs}
        missing = sorted(set(want) - set(by_id))
        if missing:
            raise SystemExit(f"--targets-file names {len(missing)} job ids not in --from, e.g. {missing[0]}")
        jobs = [{"job_id": f"replay|{spec_id(succ_spec)}|{tag}|tf={tf[:12]}|{jid}", "traj": by_id[jid],
                 "targets": sorted(set(v["targets"])), "label_source": f"targets_file:{tf[:12]}",
                 "target_types": sorted(v.get("types", []))} for jid, v in sorted(want.items())]
        print(f"--targets-file {args.targets_file} (sha256 {tf}): {len(jobs)} summaries")
        write_manifest(args.out, args, {"stage": "replay", "n_jobs": len(jobs), "targets_file_sha256": tf})
        fn = replay_fn(factory_from_args(args, succ_spec), cfg_from_args(args), args.replays,
                       include_no_compaction=not args.no_baseline, successor_spec=succ_spec,
                       arms_include=tuple(args.arms))
        run_jobs(jobs, fn, os.path.join(args.out, "replay.jsonl"), args.workers, "replay")
        return
    jobs, controls = [], []
    for t in trajs:
        tg = replay_targets(t, args.label_source)
        if tg:
            lab = t.get("labels_judge" if args.label_source == "judge" else "labels_rules") or {}
            types = sorted({c.get("type") or c.get("label") for c in lab.get("counted", [])})
            jobs.append({"job_id": f"replay|{spec_id(succ_spec)}|{tag}|{t['job_id']}", "traj": t, "targets": tg,
                         "label_source": args.label_source, "target_types": types})
        else:
            controls.append(t)
    if args.types:
        want = {f"invented_{t}" for t in args.types}
        n_before = len(jobs)
        jobs = [j for j in jobs if want & set(j["target_types"])]
        print(f"--types {' '.join(args.types)}: {len(jobs)} of {n_before} flagged summaries selected")
    if args.max_flagged and len(jobs) > args.max_flagged:
        jobs = random.Random(0).sample(jobs, args.max_flagged)
    rng = random.Random(1)
    for t in rng.sample(controls, min(args.control_n, len(controls))):
        n = len(sentences(t["summary"]["text"]))
        if n >= 3:
            # pseudo-target: a random sentence, so the arms measure generic edit effects
            jobs.append({"job_id": f"replay-control|{spec_id(succ_spec)}|{tag}|{t['job_id']}", "traj": t,
                         "targets": [rng.randrange(n)], "label_source": "control", "target_types": []})
    print(f"{sum(1 for j in jobs if j['label_source'] != 'control')} flagged, "
          f"{sum(1 for j in jobs if j['label_source'] == 'control')} control trajectories")
    write_manifest(args.out, args, {"stage": "replay", "n_jobs": len(jobs)})
    fn = replay_fn(factory_from_args(args, succ_spec), cfg_from_args(args), args.replays,
                   include_no_compaction=not args.no_baseline, successor_spec=succ_spec,
                   arms_include=tuple(args.arms))
    run_jobs(jobs, fn, os.path.join(args.out, "replay.jsonl"), args.workers, "replay")


if __name__ == "__main__":
    main()
