"""Arm 1: self-generated discovery.

Each trajectory: the model works on a task, writes its own compaction summary
at the template's compaction step, and a successor (same model by default)
continues from that summary. Every summary gets rule-based labels; add
--judge to also get LLM-judge labels.

  python scripts/run_discovery.py --model vllm:Qwen/Qwen3-8B@http://localhost:8000/v1 \
      --seeds 5 --samples 4 --out runs/disc_qwen3_8b [--judge vllm:...@...]
"""
import argparse
import os

import _path  # noqa: F401
from sid.pipeline import cfg_from_args, discovery_fn, instance_jobs
from sid.runner import common_args, factory_from_args, run_jobs, settings_tag, spec_id, write_manifest


def main():
    p = common_args(argparse.ArgumentParser(description=__doc__))
    p.add_argument("--samples", type=int, default=4, help="independent trajectories per instance")
    p.add_argument("--judge", default=None, help="judge model spec (optional)")
    args = p.parse_args()
    write_manifest(args.out, args, {"stage": "discovery"})
    jobs = instance_jobs(args, "disc", samples=args.samples, tag=f"{spec_id(args.successor) if args.successor else 'self'}|{settings_tag(args)}")
    succ = factory_from_args(args, args.successor) if args.successor else None
    judge = factory_from_args(args, args.judge) if args.judge else None
    fn = discovery_fn(factory_from_args(args), succ, cfg_from_args(args), judge,
                      model_spec=args.model, successor_spec=args.successor or "")
    run_jobs(jobs, fn, os.path.join(args.out, "trajectories.jsonl"), args.workers, "discovery")


if __name__ == "__main__":
    main()
