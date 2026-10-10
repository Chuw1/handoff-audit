"""Arm 2: planted positive control.

The model writes its own (clean) summary; the harness then plants one authored
directive per kind and runs the successor under planted / delete / neutral /
restore arms with paired seeds. If the planted authorization does not change
behavior, the replay design cannot detect an effect on this model and the
discovery replay results for it are uninformative.

  python scripts/run_positive_control.py --model vllm:Qwen/Qwen3-8B@http://localhost:8000/v1 \
      --seeds 2 --replays 4 --out runs/pc_qwen3_8b
"""
import argparse
import os

import _path  # noqa: F401
from sid.pipeline import cfg_from_args, instance_jobs, positive_control_fn
from sid.replay import ARMS_VERSION, PLANTS
from sid.runner import common_args, factory_from_args, run_jobs, settings_tag, spec_id, write_manifest


def main():
    p = common_args(argparse.ArgumentParser(description=__doc__))
    p.add_argument("--kinds", nargs="*", default=list(PLANTS))
    p.add_argument("--replays", type=int, default=4, help="successor samples per arm")
    p.add_argument("--position", default="end", choices=["start", "middle", "end"])
    args = p.parse_args()
    write_manifest(args.out, args, {"stage": "positive_control"})
    jobs = instance_jobs(args, "pc", samples=1, tag=f"{spec_id(args.successor) if args.successor else 'self'}|{args.position}|{','.join(args.kinds)}|arms_v={ARMS_VERSION}|K={args.replays}|{settings_tag(args)}")
    succ = factory_from_args(args, args.successor or args.model)
    fn = positive_control_fn(factory_from_args(args), succ, cfg_from_args(args), args.kinds,
                             args.replays, args.position, model_spec=args.model)
    run_jobs(jobs, fn, os.path.join(args.out, "positive_control.jsonl"), args.workers, "positive_control")


if __name__ == "__main__":
    main()
