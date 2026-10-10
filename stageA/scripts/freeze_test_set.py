"""Freeze / verify the test split.

  python scripts/freeze_test_set.py --write    # once, before any test-split run
  python scripts/freeze_test_set.py --verify   # before every test-split run (exit 1 on mismatch)

Two fingerprints are recorded in docs/FROZEN_TEST_SET.json:
  instances  SHA-256 of every test instance (seeds 0-4): prompt, rules, tools, initial state, ledger,
             shortcut, timing settings, canned replies. A mismatch means the test split changed.
  files      SHA-256 of the source files that define or score the test split (audit trail; a change
             here with unchanged instances is reported as a warning, e.g. a refactor).
Any change after freezing must be logged in DEVIATIONS.md with a date and reason.
"""
import argparse
import hashlib
import json
import os
import sys
import time

import _path  # noqa: F401
from sid.tasks import test_templates

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "FROZEN_TEST_SET.json")
FILES = ["sid/tasks/test_records.py", "sid/tasks/test_reports.py", "sid/tasks/test_code.py",
         "sid/tasks/test_common.py", "sid/tasks/base.py", "sid/tasks/code.py", "sid/tasks/__init__.py",
         "sid/ledger.py", "sid/tools.py", "sid/agent.py", "docs/TEST_SET_DRAFT_zh.md"]
SEEDS = range(5)


def instance_fingerprint(task) -> str:
    d = {"system": task.system_prompt, "user": task.user_prompt, "rules": task.rules, "tools": task.tool_names,
         "schemas": {n: task.family_tools[n].parameters for n in task.tool_names if n in task.family_tools},
         "state": task.initial_state, "grants": [g.__dict__ for g in task.ledger.grants],
         "default": task.ledger.default_write_status, "tempting": task.tempting_action,
         "tempting_args": task.tempting_args, "compaction": task.compaction_after_step,
         "trigger": task.compaction_trigger, "max_steps": task.max_steps, "info": task.info_reply,
         "followups": task.followups, "keywords": task.constraint_keywords,
         "external": task.external_suggestion, "honest_insufficient": task.honest_insufficient}
    return hashlib.sha256(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()


def current():
    inst = {}
    for t in test_templates():
        inst[t.template_id] = [instance_fingerprint(t.instantiate(s)) for s in SEEDS]
    files = {}
    for f in FILES:
        with open(os.path.join(ROOT, f), "rb") as fh:
            files[f] = hashlib.sha256(fh.read()).hexdigest()
    return inst, files


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true")
    g.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    inst, files = current()
    if args.write:
        if os.path.exists(OUT):
            print(f"{OUT} exists; refusing to overwrite. Log a deviation and remove it by hand if you must.")
            sys.exit(1)
        with open(OUT, "w") as f:
            json.dump({"frozen_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "n_templates": len(inst),
                       "seeds": list(SEEDS), "instances": inst, "files": files}, f, indent=1)
        print(f"wrote {OUT}: {len(inst)} templates x {len(SEEDS)} seeds")
        return
    with open(OUT) as f:
        frozen = json.load(f)
    bad = [k for k in set(frozen["instances"]) | set(inst) if frozen["instances"].get(k) != inst.get(k)]
    changed_files = [k for k in FILES if frozen["files"].get(k) != files.get(k)]
    if bad:
        print("TEST SPLIT CHANGED since freezing:", sorted(bad))
        sys.exit(1)
    if changed_files:
        print("OK: instances unchanged. Note: source files changed since freezing (log in DEVIATIONS.md if "
              "relevant):", changed_files)
    else:
        print(f"OK: test split identical to the frozen version ({frozen['frozen_at']}).")


if __name__ == "__main__":
    main()
