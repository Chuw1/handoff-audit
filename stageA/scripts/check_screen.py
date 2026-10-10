"""Exit 0 if a capability screen shows the harness works with this model, 1 otherwise.

Used as PRECHECK by slurm/submit_dev_chain.sh, so the dev runs start only after a usable screen.
This is a lighter test than the protocol gate (gate_pass), which is reported separately: the dev
chain is exploratory and its job is to show where a model fails, so it needs only
  - the report exists,
  - at most --max-error-rate of the runs ended in a harness error,
  - tool calls parse (gate.tool_calls_parse),
  - at least --min-compacted of the error-free runs reached compaction.

  python scripts/check_screen.py runs/screen_v03_qwen3_8b
"""
import argparse
import json
import os
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("screen_dir")
    ap.add_argument("--max-error-rate", type=float, default=0.10)
    ap.add_argument("--min-compacted", type=float, default=0.80)
    a = ap.parse_args()
    f = os.path.join(a.screen_dir, "screen_report.json")
    tj = os.path.join(a.screen_dir, "trajectories.jsonl")
    if os.path.exists(tj):
        # recompute with the current definitions (the stored report may predate them)
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        from sid.pipeline import screen_stats
        from sid.runner import read_jsonl
        r = screen_stats(read_jsonl(tj))
    elif os.path.exists(f):
        r = json.load(open(f))
    else:
        print(f"[check] no report at {f}")
        return 1
    n, err = r.get("n_trajectories", 0), r.get("n_errors", 0)
    ok_runs = max(1, n - err)
    checks = {
        "errors": (err / max(1, n)) <= a.max_error_rate,
        "tool_calls_parse": bool((r.get("gate") or {}).get("tool_calls_parse")),
        "compacted": r.get("n_compacted", 0) >= a.min_compacted * ok_runs,
    }
    print(f"[check] {a.screen_dir}: " + ", ".join(f"{k}={'ok' if v else 'FAIL'}" for k, v in checks.items())
          + f" (protocol gate_pass={r.get('gate_pass')}, strict={r.get('gate_pass_strict')})")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
