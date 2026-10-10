"""One-screen status of the v0.3 runs: screens, reasoning probe, dev discovery, positive control,
replay. Reads runs/ and logs/ only; prints about 20 lines per model (fits one screenshot). The
full analysis comes from scripts/analyze.py or from the raw files.

  python scripts/morning_report.py                 # both models
  python scripts/morning_report.py qwen3_8b        # one model
"""
import glob
import json
import os
import sys
from collections import defaultdict

MODELS = {"qwen3_8b": "Qwen3-8B", "gptoss_20b": "gpt-oss-20b", "qwen3_14b": "Qwen3-14B"}


def models_present():
    """The two first models always; others once any of their v0.3 runs exist."""
    have = [m for m in MODELS if glob.glob(f"runs/*_v03_{m}")]
    return [m for m in MODELS if m in ("qwen3_8b", "gptoss_20b") or m in have]


def rows(path):
    if not os.path.exists(path):
        return None
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


def latest(rs):
    """One row per job_id (a resumed run appends a new row for a job that failed before)."""
    best = {}
    for r in rs:
        j = r.get("job_id")
        if j not in best or best[j].get("error") or not r.get("error"):
            best[j] = r
    return list(best.values())


def pct(k, n):
    return f"{k}/{n} ({100 * k / n:.0f}%)" if n else f"{k}/0"


def log_lines(marker, prefixes):
    """Lines starting with one of `prefixes` from the newest job log that mentions `marker`."""
    logs = sorted(glob.glob("logs/sidA_*.out"), key=os.path.getmtime, reverse=True)
    for lg in logs:
        try:
            txt = open(lg, errors="replace").read()
        except OSError:
            continue
        if marker in txt:
            keep = [ln for ln in txt.splitlines() if ln.startswith(prefixes)]
            return os.path.basename(lg), keep
    return None, []


def screen(m):
    f = f"runs/screen_v03_{m}/screen_report.json"
    tj = f"runs/screen_v03_{m}/trajectories.jsonl"
    if os.path.exists(tj):          # recompute with the current gate definitions
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        from sid.pipeline import screen_stats
        r = screen_stats(latest(rows(tj)))
    elif os.path.exists(f):
        r = json.load(open(f))
    else:
        print("  screen v03: no report yet")
        return
    g = r.get("gate", {})
    failed = [k for k, v in g.items() if not v]
    print(f"  screen v03: gate_pass={r.get('gate_pass')} (strict {r.get('gate_pass_strict')})"
          + (f" (failed: {', '.join(failed)})" if failed else ""))
    print(f"    errors {r.get('n_errors')}/{r.get('n_trajectories')}, compacted {r.get('n_compacted')} "
          f"{r.get('compaction_reasons')}, ended {r.get('post_ended_rate', 0):.2f} "
          f"(finish tool {r.get('post_finish_tool_rate', 0):.2f})")
    print(f"    tool-name repairs {r.get('tool_name_repair_rate', 0):.3f}, format retries {r.get('format_retries')}, "
          f"empty summaries {r.get('empty_summary_rate', 0):.2f}")
    name, lines = log_lines(f"--out runs/screen_v03_{m}", ("[probe]",))
    for ln in lines:
        print("    " + ln.replace("prompt tokens ", "")[:100])
    if name and not lines:
        print(f"    (no [probe] lines in {name})")


def relabel(r):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from sid.label.rules import label_summary
    from sid.tasks import get_instance
    try:
        task = get_instance(r["template_id"], r["instance_seed"])
        snap = {"events": r["snapshot"]["env"]["events"], "step": r["snapshot"]["step"]}
        return label_summary(r["summary"]["text"], task, snap, r["snapshot"].get("pre_messages"))
    except Exception:  # noqa: BLE001 - fall back to the stored labels
        return r.get("labels_rules") or {}


def discovery(m, d=None, label="dev discovery"):
    rs = rows(f"{d or f'runs/disc_v03_{m}'}/trajectories.jsonl")
    if rs is None:
        print(f"  {label}: not run yet")
        return
    rs = latest(rs)
    ok = [r for r in rs if not r.get("error")]
    comp = [r for r in ok if r.get("compacted") and (r.get("summary") or {}).get("n_chars", 0) >= 40]
    reasons = defaultdict(int)
    for r in comp:
        reasons[r.get("compaction_reason", "step")] += 1
    lab = [relabel(r) for r in comp]          # current rules, not the ones stored at run time
    anyc = sum(1 for x in lab if x.get("any_counted"))
    types = defaultdict(int)
    for x in lab:
        for t, v in (x.get("flags") or {}).items():
            types[t] += bool(v)
    tempt = sum(1 for r in comp if (r.get("post") or {}).get("tempting_action_taken"))
    print(f"  {label}: {len(rs)} runs, {len(rs) - len(ok)} errors, {len(comp)} usable compacted, "
          f"reasons {dict(reasons)}")
    print(f"    rule-flagged (candidates, current rules): {pct(anyc, len(comp))}: "
          + ", ".join(f"{t.replace('invented_', '')} {k}" for t, k in types.items()))
    print(f"    successor took the template's tempting action: {pct(tempt, len(comp))}")


def _last_attempt(rs):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from sid.runner import last_attempt
    return last_attempt(rs)


def positive_control(m, d=None, label="positive control"):
    rs = rows(f"{d or f'runs/pc_v03_{m}'}/positive_control.jsonl")
    if rs is None:
        print(f"  {label}: not run yet")
        return
    rs = _last_attempt(rs)
    n_err = sum(1 for r in rs if r.get("error"))
    rs = [r for r in rs if not r.get("error") and not r.get("skipped")]      # v0.3.9: errors are not counted in n
    cell = defaultdict(lambda: [0, 0, 0, 0])
    for r in rs:
        c = cell[(r.get("plant_kind"), r.get("arm"))]
        c[0] += bool(r.get("tempting_action_taken"))
        c[1] += bool(r.get("any_violation"))
        c[2] += bool(r.get("success"))
        c[3] += 1
    print(f"  {label}, planted / claim-correct / delete / restore (tempting action T, violation V, success S):"
          + (f"  [{n_err} error rows left out]" if n_err else ""))
    for kind in ("authorization", "restriction", "concealment", "persona"):
        if (kind, "planted") not in cell:
            continue
        parts = [f"{ {'claim_correct': 'clm'}.get(arm, arm[:4]) } T{cell[(kind, arm)][0]} V{cell[(kind, arm)][1]} S{cell[(kind, arm)][2]}/{cell[(kind, arm)][3]}"
                 for arm in ("planted", "claim_correct", "delete", "restore") if (kind, arm) in cell]
        print(f"    {kind[:11]:11s} " + " | ".join(parts))


def replay(m, d=None, label="replay"):
    rs = rows(f"{d or f'runs/replay_v03_{m}'}/replay.jsonl")
    if rs is None:
        print(f"  {label}: not run yet")
        return
    # v0.3.9: error rows are left out of every count (before, a failed job showed up as a "source summary"
    # with no id, and a failed run would have been counted in its arm's n); they are reported on their own
    rs = _last_attempt(rs)       # a re-run job's old rows are not counted twice
    job_err = [r for r in rs if r.get("error") and not r.get("run_error")]
    run_err = [r for r in rs if r.get("error") and r.get("run_error")]
    rs = [r for r in rs if not r.get("error")]
    src = {r.get("source_job_id") for r in rs}
    cell = defaultdict(lambda: [0, 0, 0, 0])
    for r in rs:
        flagged = not str(r.get("job_id", "")).startswith("replay-control")
        c = cell[(flagged, r.get("arm"))]
        c[0] += bool(r.get("tempting_action_taken"))
        c[1] += bool(r.get("any_violation"))
        c[2] += bool(r.get("success"))
        c[3] += 1
    print(f"  {label}: {len(src)} source summaries, {len(rs)} successor runs (tempting action T / any violation V "
          f"/ success S, of n):")
    if job_err or run_err:
        print(f"    ERRORS: {len(job_err)} whole source summaries failed (no rows), {len(run_err)} single runs failed "
              f"(their pairs are dropped)")
    order = ["original", "claim_correct", "ledger_correct", "correct", "delete", "neutral", "restore", "edit_control",
             "no_compaction", "pressure"]
    short = {"original": "orig", "claim_correct": "clm", "ledger_correct": "ldg", "correct": "corr", "delete": "del",
             "neutral": "neut", "restore": "rest", "edit_control": "edit", "no_compaction": "nocomp", "pressure": "press"}
    conf = defaultdict(lambda: [0, 0])
    for r in rs:
        if "n_confirm_requests" in r:
            flagged = not str(r.get("job_id", "")).startswith("replay-control")
            c = conf[(flagged, r.get("arm"))]
            c[0] += r["n_confirm_requests"] > 0
            c[1] += 1
    for flagged, label in ((True, "flagged"), (False, "controls")):
        arms = [a for a in order if (flagged, a) in cell]
        if arms and conf:      # v0.3.6 rows: the successor asked for a confirmation (C)
            print(f"    {label:8s} C " + " ".join(f"{short[a]} {conf[(flagged, a)][0]}/{conf[(flagged, a)][1]}"
                                             for a in arms if (flagged, a) in conf))
        for j, key in ((0, "T"), (1, "V"), (2, "S")):
            if arms:
                print(f"    {label:8s} {key} " + " ".join(f"{short[a]} {cell[(flagged, a)][j]}/{cell[(flagged, a)][3]}"
                                                     for a in arms))


def main(which):
    for m in which:
        print(f"== {MODELS.get(m, m)}")
        name, lines = log_lines(f"--out runs/disc_v03_{m}", ("[check]", "SKIP", "=== stage", "done:"))
        if name:
            print(f"  dev chain log {name}: {len([x for x in lines if x.startswith('done:')])}/3 steps done")
            for ln in lines:
                if ln.startswith(("[check]", "SKIP")):
                    print("    " + ln[:100])
        screen(m)
        discovery(m)
        positive_control(m)
        replay(m)
        # v0.3.4 supplementary runs (slurm/submit_v034.sh)
        for d in sorted(glob.glob(f"runs/disc_v034_{m}*")):
            discovery(m, d, os.path.basename(d))
        for d in sorted(glob.glob(f"runs/replay_v034_{m}*") + glob.glob(f"runs/replay_v036_{m}*") +
                        glob.glob(f"runs/replay_v037_{m}*") + glob.glob(f"runs/replay_v038_{m}*") +
                        glob.glob(f"runs/replay_v039_{m}*")):
            replay(m, d, os.path.basename(d))
        # v0.3.10 overnight runs (slurm/submit_overnight_v0310.sh)
        for d in sorted(glob.glob(f"runs/disc_v039x_{m}") + glob.glob(f"runs/disc_h3*_{m}")):
            discovery(m, d, os.path.basename(d))
        if os.path.isdir(f"runs/pc_v039_{m}"):
            positive_control(m, f"runs/pc_v039_{m}", "pc_v039")
        for d in sorted(glob.glob(f"runs/replay_v039x_*_{m}") + glob.glob(f"runs/replay_x_{m}_from_*")):
            replay(m, d, os.path.basename(d))
        for f in sorted(glob.glob(f"runs/mon_{m}_on_*/monitor_report_*.json")):
            monitor(f)


def monitor(path):
    """v0.3.10: one line per view of a monitor report (exploratory on dev: templates split in half)."""
    try:
        rep = json.load(open(path))
    except (OSError, ValueError):
        print(f"  {path}: unreadable")
        return
    print(f"  {os.path.basename(os.path.dirname(path))}: {rep.get('note', '')[:60]}; eval n={rep.get('n_eval')}, "
          f"positives {rep.get('positives_eval')}")
    for v, x in (rep.get("views") or {}).items():
        t = x.get("test") or {}
        print(f"    {v:8s} " + ", ".join(f"{k} {t[k]:.2f}" if isinstance(t.get(k), float) else f"{k} {t.get(k)}"
                                       for k in ("recall", "precision", "fpr") if k in t))


if __name__ == "__main__":
    main(sys.argv[1:] or models_present())
