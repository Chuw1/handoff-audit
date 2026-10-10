"""Capability screen: can this model run the harness at all?

Runs ~30 trajectories (dev templates, round-robin) and reports tool-call parse
rates, whether compaction is reached, summary truncation, finish rate, success,
token use and latency. Only models that pass the gate go on to discovery.

  python scripts/run_capability_screen.py --model vllm:Qwen/Qwen3-8B@http://localhost:8000/v1 \
      --out runs/screen_qwen3_8b --n 30
"""
import argparse
import json
import os

import _path  # noqa: F401
from sid.pipeline import cfg_from_args, discovery_fn, screen_stats
from sid.runner import common_args, factory_from_args, read_jsonl, run_jobs, settings_tag, spec_id, write_manifest
from sid.tasks import get_templates


def main():
    p = common_args(argparse.ArgumentParser(description=__doc__))
    p.add_argument("--n", type=int, default=30)
    args = p.parse_args()
    write_manifest(args.out, args, {"stage": "capability_screen"})
    ts = get_templates(args.split, args.families, args.templates)
    jobs = []
    for i in range(args.n):
        t = ts[i % len(ts)]
        s = args.seed_offset + i // len(ts)
        jobs.append({"job_id": f"screen|{spec_id(args.model)}|{t.template_id}|s{s}|r0|{settings_tag(args)}",
                     "template_id": t.template_id, "instance_seed": s, "sample": 0})
    fn = discovery_fn(factory_from_args(args), None, cfg_from_args(args), model_spec=args.model)
    out = os.path.join(args.out, "trajectories.jsonl")
    info = run_jobs(jobs, fn, out, args.workers, "screen")
    stats = screen_stats(read_jsonl(out))
    stats["wall_seconds_this_run"] = info["seconds"]
    if info["seconds"] > 0 and info["ok"]:
        stats["trajectories_per_hour_this_run"] = info["ok"] / info["seconds"] * 3600
    with open(os.path.join(args.out, "screen_report.json"), "w") as f:
        json.dump(stats, f, indent=1)
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
