"""Run one trajectory and print it in full (for reading what a model actually does).

  python scripts/show_one.py --model mock:self_authorize --template R1_dedupe_pending
  python scripts/show_one.py --model vllm:Qwen/Qwen3-8B@http://localhost:8000/v1 --template C2_deploy_pending
"""
import argparse
import json
import textwrap

import _path  # noqa: F401
from sid.agent import EpisodeConfig, run_episode
from sid.label.rules import label_summary
from sid.runner import model_factory
from sid.tasks import get_templates


def show_turns(turns, width=110):
    for t in turns:
        if (t.get("reasoning") or "").strip():
            print(textwrap.indent(textwrap.shorten(t["reasoning"], 600), "    [reasoning] "))
        if (t.get("content") or "").strip():
            print(textwrap.indent(textwrap.fill(t["content"], width), "    [text] "))
        cut = False
        for tc in t.get("tool_calls") or []:
            fb = " (parsed from text)" if t.get("parse_fallback") else ""
            if tc.get("raw_name"):
                fb += f" (name repaired from {tc['raw_name'][:60]!r})"
            if t.get("intercepted_finish") and (cut or tc["name"] == "finish"):
                cut = True
                fb += "  <- NOT EXECUTED: compaction happened here (v0.3 rule)"
            print(f"    -> {tc['name']}({tc['arguments'][:300]}){fb}")
        if t.get("intercepted_finish") and not t.get("tool_calls"):
            print("    <- final text reply NOT KEPT: compaction happened here (v0.3 rule)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--successor", default=None)
    ap.add_argument("--template", required=True, help="template id suffix, e.g. R1_dedupe_pending")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--episode-seed", type=int, default=1)
    ap.add_argument("--json", default=None, help="also save the trajectory here")
    args = ap.parse_args()
    t = get_templates("dev", ids=[args.template])[0]
    task = t.instantiate(args.seed)
    writer = model_factory(args.model)()
    succ = model_factory(args.successor)() if args.successor else None
    tr = run_episode(task, writer, succ, seed=args.episode_seed, cfg=EpisodeConfig())
    print("=" * 100)
    print(task.instance_id, "| tempting:", task.tempting_action)
    print("SYSTEM:\n" + task.system_prompt)
    print("USER:\n" + task.user_prompt)
    print("-" * 40, "before compaction")
    show_turns(tr["turns_pre"])
    if tr["compacted"]:
        print("-" * 40, "SUMMARY", "(truncated)" if tr["summary"]["truncated"] else "")
        print(tr["summary"]["text"])
        lab = label_summary(tr["summary"]["text"], task, tr["snapshot"]["env"], tr["snapshot"]["pre_messages"])
        print("-" * 40, "rule labels")
        for c in lab["candidates"]:
            print(f"  [{c['type']}] supported={c['supported']} copied={c['copied_from_input']}: {c['text']}")
        print("  dropped rules:", [d["rule_idx"] for d in lab["dropped_constraints"]])
        print("-" * 40, "after compaction")
        show_turns(tr["post"]["turns"])
        print("-" * 40)
        print("violations after compaction:", json.dumps(
            [{k: v.get(k) for k in ("type", "tool", "target", "executed")} for v in tr["violations_post"]]))
        print("tempting action taken:", tr["post"]["tempting_action_taken"], "| success:", tr["success"])
    else:
        print("(finished before the compaction step)")
    if args.json:
        with open(args.json, "w") as f:
            json.dump(tr, f, indent=1, default=str)


if __name__ == "__main__":
    main()
