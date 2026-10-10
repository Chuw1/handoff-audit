"""Print saved trajectories from a JSONL file in readable form.

  python3 scripts/print_traj.py runs/screen_qwen3_8b/trajectories.jsonl --n 3
  python3 scripts/print_traj.py runs/disc_x/trajectories.jsonl --flagged --n 5
  python3 scripts/print_traj.py runs/disc_x/trajectories.jsonl --template R1_dedupe_pending
"""
import argparse

import _path  # noqa: F401
from show_one import show_turns
from sid.runner import read_jsonl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--template", default=None)
    ap.add_argument("--flagged", action="store_true", help="only summaries with a counted rule label")
    ap.add_argument("--violations", action="store_true", help="only trajectories with a post-compaction violation")
    ap.add_argument("--no-turns", action="store_true", help="print summaries and labels only")
    args = ap.parse_args()
    shown = 0
    for t in read_jsonl(args.path):
        if t.get("error") or not t.get("compacted"):
            continue
        if args.template and not t["template_id"].endswith(args.template):
            continue
        if args.flagged and not (t.get("labels_rules") or {}).get("any_counted"):
            continue
        if args.violations and not t.get("violations_post"):
            continue
        print("=" * 100)
        print(t["job_id"])
        print("USER:", t.get("user_prompt"))
        if not args.no_turns:
            print("-" * 30, "before compaction")
            show_turns(t["turns_pre"])
        print("-" * 30, "SUMMARY", "(truncated)" if t["summary"]["truncated"] else "")
        print(t["summary"]["text"] or "(empty)")
        for c in (t.get("labels_rules") or {}).get("candidates", []):
            print(f"  [{c['type']}] supported={c['supported']} copied={c['copied_from_input']}: {c['text']}")
        if not args.no_turns:
            print("-" * 30, "after compaction")
            show_turns(t["post"]["turns"])
        print("violations after compaction:",
              [(v["type"], v["tool"], v.get("target"), v.get("executed")) for v in t.get("violations_post", [])])
        print("tempting action taken:", t["post"]["tempting_action_taken"], "| success:", t.get("success"))
        shown += 1
        if shown >= args.n:
            break
    if not shown:
        print("no matching trajectories")


if __name__ == "__main__":
    main()
