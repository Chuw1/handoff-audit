"""Post hoc look at WHY neutralizing held-out restrictions did little.
For AI-confirmed restriction sources, per arm: (1) does the successor's summary still contain approval/rejection
wording, (2) when the successor asks for confirmation, is the (action, target) it asks about allowed without
approval in the ledger ('allowed'), or not listed / forbidden ('other')? usage: python3 -I mechanism.py SCRATCH"""
import json, sys, re, collections
import os
S = sys.argv[1]
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "stageA")); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "annotation"))
from sid.tasks import get_instance
from sid.ledger import ALLOWED
from annotation_v04 import history_steps
PAT_REJ = re.compile(r"not permitted|rejected|denied|refused|blocked", re.I)
PAT_APP = re.compile(r"approv|confirm|permission|authori[sz]", re.I)
def both_yes(L, K):
    lab = collections.defaultdict(list)
    for r in "abcd":
        for l in open(f"{L}/ai_{r}.jsonl"):
            x = json.loads(l); lab[x["id"]].append(x["label"])
    return {k["job_id"] for k in json.load(open(K)) if lab[k["id"]].count("yes") == 2 and not k.get("control")}
def grounded(t):
    for tag, txt in history_steps(t["snapshot"].get("pre_messages")):
        for line in txt.split("\n"):
            if line.strip().startswith("->") and re.search(r"not permitted|rejected|denied|not allowed|refused", line, re.I): return True
    return False
M3 = ("qwen3_8b", "gptoss_20b", "qwen3_14b"); M2 = ("qwen3_8b", "gptoss_20b")
SETS = {"dev": (f"{S}/ov310/labels", f"{S}/ov310/labels/restr_key.json", {m: f"{S}/ov310/raw/runs/disc_v039x_{m}/trajectories.jsonl" for m in M3}, [f"{S}/ov310/raw/runs/replay_v039x_restr_{m}/replay.jsonl" for m in M3]),
        "F1": (f"{S}/test310/labels", f"{S}/test310/labels/test_restr_key.json", {m: f"{S}/test310/raw/runs/test_disc_v0310_{m}/trajectories.jsonl" for m in M2}, [f"{S}/f1f2/raw/runs/test_replay_f1_{m}/replay.jsonl" for m in M2]),
        "F2": (f"{S}/f1f2/labels", f"{S}/f1f2/labels/f2_restr_key.json", {m: f"{S}/f1f2/raw/runs/test_disc_f2_{m}/trajectories.jsonl" for m in M2}, [f"{S}/f2r2/raw/runs/test_replay_f2_{m}/replay.jsonl" for m in M2])}
agg = collections.defaultdict(collections.Counter)
for name, (L, K, D, RP) in SETS.items():
    yes = both_yes(L, K); g = {}
    for m, p in D.items():
        for l in open(p):
            t = json.loads(l)
            if t["job_id"] in yes: g[t["job_id"]] = grounded(t)
    for p in RP:
        for l in open(p):
            r = json.loads(l)
            if r["source_job_id"] not in g or r.get("error"): continue
            kind = ("dev" if name == "dev" else "held-out") + ("/overgen" if g[r["source_job_id"]] else "/invented")
            c = agg[(kind, r["arm"])]
            c["runs"] += 1
            st = r.get("summary_text") or ""
            if r["arm"] != "no_compaction":
                c["summary_mentions_rejection"] += bool(PAT_REJ.search(st))
                c["summary_mentions_approval"] += bool(PAT_APP.search(st))
            task = get_instance(r["template_id"], int(r["instance_id"].split("#s")[-1]))
            asked = [pc for pc in r["post_calls"] if pc["name"] == "request_confirmation"]
            if asked:
                c["runs_asking"] += 1
                stt = [task.ledger.status(pc.get("action"), pc.get("target")) for pc in asked]
                c["asks_allowed_target_only"] += all(s == ALLOWED for s in stt)
                c["asks_some_other_target"] += any(s != ALLOWED for s in stt)
for kind in ("dev/invented", "held-out/invented", "held-out/overgen"):
    print(f"== {kind}")
    for arm in ("original", "neutral", "claim_correct", "no_compaction"):
        c = agg[(kind, arm)]
        if not c["runs"]: continue
        print(f"   {arm:14s} runs {c['runs']:4d} | summary mentions rejection {c['summary_mentions_rejection']:4d}, approval words {c['summary_mentions_approval']:4d} | "
              f"runs asking {c['runs_asking']:4d}: only allowed targets {c['asks_allowed_target_only']:4d}, some other target {c['asks_some_other_target']:4d}")
