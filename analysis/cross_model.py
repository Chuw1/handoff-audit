"""Cross-model 2x2: same flagged dev summaries (disc_v03, seeds 0-4) continued by the writer itself (v0.3.9 replay)
and by the other model (v0.3.10 replay_x). Labels: rule layer, and fixture layer (A, plus B for Qwen3-8B; the
5 script-only labels are not used). S=<scratchpad> python3 -I cross310.py"""
import json, os
from math import comb
from collections import defaultdict
S = os.environ["S"]
FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "stageA", "tests", "fixtures")
A = {}
for l in open(f"{FX}/dev_20261002_three_models_hand.jsonl"):
    r = json.loads(l); A[(r["model"], r["summary"].strip())] = r["hand_label"]
B = {}
for l in open(f"{FX}/dev_20261002_qwen3_8b_flagged.jsonl"):
    r = json.loads(l); B[r["summary"].strip()] = "true" if r["hand_label_true"] else "false"
ARMS = ["original", "neutral", "delete", "edit_control", "claim_correct", "ledger_correct", "restore", "no_compaction"]
def sign_p(pos, neg):
    n = pos + neg
    if n == 0: return 1.0
    k = min(pos, neg); return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)
def load(path):
    per = defaultdict(lambda: defaultdict(list)); info = {}; nerr = 0
    for l in open(path):
        r = json.loads(l)
        if r.get("error") or r.get("run_error"):
            nerr += 1; continue
        if r["job_id"].startswith("replay-control"): continue
        p = r["source_job_id"].split("|"); n = (p[-3].split(":")[-1], p[-2], p[-1])
        per[n][r["arm"]].append(r)
        if r["arm"] == "original":
            info[n] = (r["summary_text"].strip(), ",".join(x.replace("invented_", "") for x in (r.get("target_types") or [])))
    return per, info, nerr
F = {"confirm": lambda r: r["n_confirm_requests"] > 0, "exec_unauth": lambda r: r["n_executed_unauth"] > 0}
def row(per, srcs, out, a):
    f = F[out]
    o = {s: sum(map(f, per[s]["original"])) / len(per[s]["original"]) for s in srcs}
    num = sum(sum(map(f, per[s][a])) for s in srcs); den = sum(len(per[s][a]) for s in srcs)
    if a == "original": return f"{num}/{den}"
    d = [o[s] - sum(map(f, per[s][a])) / len(per[s][a]) for s in srcs]
    pos = sum(v > 1e-12 for v in d); neg = sum(v < -1e-12 for v in d)
    return f"{num}/{den} ({pos}/{neg}, p={sign_p(pos, neg):.3g})"
OLD, NEW = f"{S}/r039/runs", f"{S}/ov310/raw/runs"
for writer, other in (("qwen3_8b", "gptoss_20b"), ("gptoss_20b", "qwen3_8b")):
    same, info_s, e1 = load(f"{OLD}/replay_v039_{writer}/replay.jsonl")
    cross, info_c, e2 = load(f"{NEW}/replay_x_{other}_from_{writer}/replay.jsonl")
    common = [n for n in same if n in cross and all(same[n][a] for a in ARMS) and all(cross[n][a] for a in ARMS)]
    only_s = sorted(set(same) - set(common)); only_c = sorted(set(cross) - set(common))
    assert all(info_s[n][0] == info_c[n][0] for n in common), "summary text differs"
    print(f"\n######## writer {writer}: common sources {len(common)}; only same-model {only_s}; only cross {only_c}; error rows {e1}/{e2}")
    def lab(n):
        t = info_s[n][0]
        return A.get((writer, t)) or (B.get(t) if writer == "qwen3_8b" else None) or "-"
    for typ, out in (("restriction", "confirm"), ("authorization", "exec_unauth")):
        for tier in ("rule", "fixture_true"):
            srcs = [n for n in common if typ in info_s[n][1] and (tier == "rule" or lab(n) == "true")]
            if not srcs: continue
            print(f"--- {typ} / {tier}: {len(srcs)} sources, outcome {out}")
            print(f"   {'arm':15s} {'successor = writer ('+writer+')':42s} successor = {other}")
            for a in ARMS:
                print(f"   {a:15s} {row(same, srcs, out, a):42s} {row(cross, srcs, out, a)}")
