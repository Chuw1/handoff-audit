"""Copies a run file without the half-written line a crash can leave at its end, and prints the number of
jobs that have only error rows. usage: python3 diagnose/clean_runs.py IN.jsonl OUT_DIR"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "stageA"))
from sid.runner import read_jsonl  # noqa: E402

rows = read_jsonl(sys.argv[1])
bad = {r["job_id"] for r in rows if r.get("error")} - {r["job_id"] for r in rows if not r.get("error")}
os.makedirs(sys.argv[2], exist_ok=True)
with open(os.path.join(sys.argv[2], "trajectories.jsonl"), "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
print(len(bad))
