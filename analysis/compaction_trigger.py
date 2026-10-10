"""Post hoc: when did compaction happen, and does the neutral-edit effect differ by it?
Compaction is triggered at a fixed step ('step'), when the agent calls finish ('before_finish'; the call is
intercepted), or right after a revocation ('revocation'). For AI-confirmed restriction sources, this script
reports (1) the share of each trigger among all compacted discovery episodes, (2) sources per trigger,
(3) original vs neutral confirmation requests per trigger and set, (4) the same split by kind of error
(overgeneralized = the pre-compaction history contains a rejected or refused tool result), and (5) for
held-out overgeneralized sources, how many original-arm runs asked again about a target whose request had
already been rejected before compaction. usage: python3 -I compaction_trigger.py DATA_DIR"""
import json, sys, os, re, collections
from math import comb
S = sys.argv[1]
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(H, "..", "stageA")); sys.path.insert(0, os.path.join(H, "..", "annotation"))
from sid.tasks import get_instance
from sid.ledger import ALLOWED
from annotation_v04 import history_steps

def sp(a, b):
    n = a + b; k = min(a, b); return min(1, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1
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
def rejected_requests(t):
    """(action, target) pairs of request_confirmation calls answered 'Request rejected' before compaction."""
    out, pend = set(), {}
    for m in t["snapshot"].get("pre_messages") or []:
        if m.get("role") == "assistant":
            for tc in m.get("tool_calls") or []:
                f = tc.get("function", {})
                if f.get("name") == "request_confirmation":
                    try: a = json.loads(f.get("arguments") or "{}")
                    except ValueError: a = {}
                    pend[tc.get("id")] = (str(a.get("action", "")).lower(), str(a.get("target", "")).lower())
        elif m.get("role") == "tool" and m.get("tool_call_id") in pend:
            if str(m.get("content", "")).startswith("Request rejected"): out.add(pend[m["tool_call_id"]])
    return out

M3 = ("qwen3_8b", "gptoss_20b", "qwen3_14b"); M2 = ("qwen3_8b", "gptoss_20b")
DISC = {"dev": {m: f"{S}/ov310/raw/runs/disc_v039x_{m}/trajectories.jsonl" for m in M3},
        "test": {m: f"{S}/test310/raw/runs/test_disc_v0310_{m}/trajectories.jsonl" for m in M2},
        "F2": {m: f"{S}/f1f2/raw/runs/test_disc_f2_{m}/trajectories.jsonl" for m in M2},
        "F3": {"gptoss_120b": f"{S}/f3/raw/runs/test_disc_f3_gptoss_120b/trajectories.jsonl"},
        "F3c": {"qwen3_235b": f"{S}/f3c/raw/runs/test_disc_f3c_qwen3_235b/trajectories.jsonl"}}
LAB = {"dev": (f"{S}/ov310/labels", f"{S}/ov310/labels/restr_key.json"),
       "test": (f"{S}/test310/labels", f"{S}/test310/labels/test_restr_key.json"),
       "F2": (f"{S}/f1f2/labels", f"{S}/f1f2/labels/f2_restr_key.json"),
       "F3": (f"{S}/f3/labels", f"{S}/f3/labels/f3_restr_key.json"),
       "F3c": (f"{S}/f3c/labels", f"{S}/f3c/labels/f3c_restr_key.json")}
REPLAY = {"Dev": ("dev", [f"{S}/ov310/raw/runs/replay_v039x_restr_{m}/replay.jsonl" for m in M3]),
          "Test": ("test", [f"{S}/test310/raw/runs/test_replay_restr_{m}/replay.jsonl" for m in M2]),
          "F1": ("test", [f"{S}/f1f2/raw/runs/test_replay_f1_{m}/replay.jsonl" for m in M2]),
          "F2": ("F2", [f"{S}/f2r2/raw/runs/test_replay_f2_{m}/replay.jsonl" for m in M2]),
          "F3": ("F3", [f"{S}/f3r2/raw/runs/test_replay_f3_gptoss_120b/replay.jsonl"]),
          "F3c": ("F3c", [f"{S}/f3cr2/raw/runs/test_replay_f3c_qwen3_235b/replay.jsonl"])}
TR = {"step": "step", "before_finish": "finish", "revocation": "revocation"}

print("== (1) compaction trigger among compacted discovery episodes")
for name, d in DISC.items():
    for m, p in d.items():
        c = collections.Counter()
        for l in open(p):
            t = json.loads(l)
            if t.get("error") or not t.get("compacted"): continue
            c[TR.get(t.get("compaction_reason"), str(t.get("compaction_reason")))] += 1
        n = sum(c.values())
        print(f"   {name:4s} {m:12s} compacted {n:5d}: " + ", ".join(f"{k} {v} ({100 * v / n:.0f}%)" for k, v in sorted(c.items())))

src = {}  # set -> job_id -> (trigger, overgeneralized, rejected requests)
print("== (2) AI-confirmed restriction sources by trigger")
for name, d in DISC.items():
    yes = both_yes(*LAB[name]); src[name] = {}
    for m, p in d.items():
        for l in open(p):
            t = json.loads(l)
            if t["job_id"] in yes:
                src[name][t["job_id"]] = (TR.get(t.get("compaction_reason"), str(t.get("compaction_reason"))), grounded(t), rejected_requests(t), m)
    c = collections.Counter((v[0], "overgeneralized" if v[1] else "invented") for v in src[name].values())
    print(f"   {name:4s} {len(src[name])} sources: " + ", ".join(f"{k[0]}/{k[1]} {v}" for k, v in sorted(c.items())))

def load(paths, keep):
    per = collections.defaultdict(lambda: collections.defaultdict(list))
    for p in paths:
        for l in open(p):
            r = json.loads(l)
            if r.get("error") or r.get("run_error") or r["job_id"].startswith("replay-control"): continue
            if r["source_job_id"] in keep: per[r["source_job_id"]][r["arm"]].append(r)
    return per
def compare(per, ids, arm="neutral"):
    ks = [k for k in ids if per[k]["original"] and per[k][arm]]
    f = lambda r: r["n_confirm_requests"] > 0
    o = sum(sum(map(f, per[k]["original"])) for k in ks); a = sum(sum(map(f, per[k][arm])) for k in ks)
    no = sum(len(per[k]["original"]) for k in ks); na = sum(len(per[k][arm]) for k in ks)
    d = [sum(map(f, per[k]["original"])) / len(per[k]["original"]) - sum(map(f, per[k][arm])) / len(per[k][arm]) for k in ks]
    dn = sum(x > 1e-12 for x in d); up = sum(x < -1e-12 for x in d)
    return len(ks), o, no, a, na, dn, up, sp(dn, up)

print("== (3) original vs neutral, runs with a confirmation request, by trigger")
pooled = collections.defaultdict(lambda: collections.defaultdict(list)); pooled_ids = {}
for name, (sname, paths) in REPLAY.items():
    per = load(paths, src[sname])
    for trig in ("step", "finish", "revocation"):
        ids = [k for k, v in src[sname].items() if v[0] == trig]
        if not ids: continue
        n, o, no, a, na, dn, up, p = compare(per, ids)
        if n: print(f"   {name:4s} {trig:10s} {n:3d} sources: original {o}/{no} -> neutral {a}/{na}; down {dn} up {up} p={p:.3g}")
    if name in ("F1", "F2"):
        for k, v in per.items(): pooled[(name, k)] = v
        for k, v in src[sname].items(): pooled_ids[(name, k)] = v

print("== (4) F1 + F2 pooled, by trigger and kind of error (held-out)")
for trig in ("step", "finish"):
    for g, gname in ((None, "all"), (True, "overgeneralized"), (False, "invented")):
        ids = [k for k, v in pooled_ids.items() if v[0] == trig and (g is None or v[1] == g)]
        n, o, no, a, na, dn, up, p = compare(pooled, ids)
        c = compare(pooled, ids, "claim_correct")
        print(f"   {trig:7s} {gname:16s} {n:3d} source replays: original {o}/{no} -> neutral {a}/{na}; down {dn} up {up} p={p:.3g}; claim_correct {c[3]}/{c[4]}")

print("== (5) held-out overgeneralized sources (F1 + F2), original arm: what the successor asked about")
c = collections.Counter()
for (name, k), arms in pooled.items():
    trig, over, rej, _m = pooled_ids[(name, k)]
    if not over: continue
    for r in arms["original"]:
        asked = [pc for pc in r["post_calls"] if pc["name"] == "request_confirmation"]
        if not asked: continue
        task = get_instance(r["template_id"], int(r["instance_id"].split("#s")[-1]))
        c["runs asking"] += 1
        other = [pc for pc in asked if task.ledger.status(pc.get("action"), pc.get("target")) != ALLOWED]
        if other:
            c["asked about some target the ledger does not allow"] += 1
            if any((str(pc.get("action", "")).lower(), str(pc.get("target", "")).lower()) in rej for pc in other):
                c["of these, asked again about a target already rejected before compaction"] += 1
for k, v in c.items(): print(f"   {k}: {v}")

print("== (6) F1 + F2 pooled, by trigger within each model")
for m in M2:
    for trig in ("step", "finish"):
        ids = [k for k, v in pooled_ids.items() if v[0] == trig and v[3] == m]
        n, o, no, a, na, dn, up, p = compare(pooled, ids)
        print(f"   {m:11s} {trig:7s} {n:3d} source replays: original {o}/{no} -> neutral {a}/{na}; down {dn} up {up} p={p:.3g}")
