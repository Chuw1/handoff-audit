"""Print capability-screen reports side by side.

  python scripts/compare_screens.py runs/screen_qwen3_8b runs/screen_v03_qwen3_8b runs/screen_v03_gptoss_20b
"""
import json
import os
import sys


def flat(d, prefix=""):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(flat(v, prefix + k + "."))
        else:
            out[prefix + k] = v
    return out


def fmt(v):
    if isinstance(v, float):
        return f"{v:.3f}"
    return "-" if v is None else str(v)


def main(paths):
    cols, reps = [], []
    for p in paths:
        f = p if p.endswith(".json") else os.path.join(p, "screen_report.json")
        if not os.path.exists(f):
            print("MISSING:", f)
            continue
        name = os.path.basename(os.path.dirname(f) if p.endswith(".json") else p.rstrip("/"))
        cols.append(name[len("screen_"):] if name.startswith("screen_") else name)
        reps.append(flat(json.load(open(f))))
    if not reps:
        return
    keys = []
    for r in reps:
        keys += [k for k in r if k not in keys]
    w = max(14, *(len(c) + 2 for c in cols))
    print(f"{'':34s}" + "".join(f"{c[-w + 1:]:>{w}s}" for c in cols))
    for k in keys:
        print(f"{k[:34]:34s}" + "".join(f"{fmt(r.get(k)):>{w}s}" for r in reps))


if __name__ == "__main__":
    main(sys.argv[1:])
