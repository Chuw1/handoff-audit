"""Human check on the test split: agreement between the human reader(s) and the AI readers, and the planned
sensitivity check (primary test restricted to the human-checked subset).
usage: python3 -I hc_agreement.py LABELS_DIR HUMAN_JSONL RUNS_DIR [HUMAN2_JSONL]
  LABELS_DIR: test310/labels (ai_[abcd].jsonl, test_{auth,restr}_key.json); human_check_60_key.json next to HUMAN_JSONL
  RUNS_DIR: test310/raw/runs (test_replay_restr_<m>/replay.jsonl, test_replay_auth_<m>/replay.jsonl)"""
import json, sys, os, collections
from math import comb
L, HF, R = sys.argv[1], sys.argv[2], sys.argv[3]
H2F = sys.argv[4] if len(sys.argv) > 4 else None

def sign_p(a, b):
    n = a + b; k = min(a, b)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0
def kappa(pairs, cats):
    n = len(pairs); po = sum(x == y for x, y in pairs) / n
    ca = collections.Counter(x for x, _ in pairs); cb = collections.Counter(y for _, y in pairs)
    pe = sum(ca[c] * cb[c] for c in cats) / n / n
    return ((po - pe) / (1 - pe) if pe < 1 else 1.0), po

ai = collections.defaultdict(dict)
for r in "abcd":
    for l in open(f"{L}/ai_{r}.jsonl"):
        x = json.loads(l); ai[x["id"]][r] = x
key = {}
for k in ("auth", "restr"):
    for x in json.load(open(f"{L}/test_{k}_key.json")): key[x["id"]] = x
sample = json.load(open(os.path.join(os.path.dirname(os.path.abspath(HF)), "human_check_60_key.json")))["sample"]
hum = {json.loads(l)["id"]: json.loads(l) for l in open(HF)}
assert set(hum) == set(sample), "human file does not cover the sample"
h2 = {json.loads(l)["id"]: json.loads(l) for l in open(H2F)} if H2F else {}

def ai_pair(i):
    d = ai[i]; a = d.get("a", d.get("c")); b = d.get("b", d.get("d")); return a, b
def ai_conf(i):
    a, b = ai_pair(i); return a["label"] == "yes" and b["label"] == "yes"

print(f"items: {len(sample)} (authorization {sum(i.startswith('U') for i in sample)}, restriction {sum(i.startswith('V') for i in sample)}); "
      f"unflagged controls among them: {sum(1 for i in sample if key[i].get('control'))}")
print("human labels:", dict(collections.Counter(hum[i]['label'] for i in sample)))
for kind, pre in (("all", ""), ("authorization", "U"), ("restriction", "V")):
    ids = [i for i in sample if i.startswith(pre)]
    if not ids: continue
    hy = [hum[i]["label"] == "yes" for i in ids]; ay = [ai_conf(i) for i in ids]
    tp = sum(h and a for h, a in zip(hy, ay)); fp = sum((not h) and a for h, a in zip(hy, ay))
    fn = sum(h and not a for h, a in zip(hy, ay)); tn = sum((not h) and not a for h, a in zip(hy, ay))
    k, po = kappa([("y" if h else "n", "y" if a else "n") for h, a in zip(hy, ay)], ("y", "n"))
    print(f"== {kind}: n={len(ids)}  human yes & AI-confirmed {tp}, AI only {fp}, human only {fn}, neither {tn}; "
          f"agreement {po:.3f}, Cohen kappa {k:.3f}")
    if tp + fp: print(f"   AI-confirmed items the human also labeled yes (precision vs human): {tp}/{tp + fp}")
    if tp + fn: print(f"   human-yes items that were AI-confirmed: {tp}/{tp + fn}")
    for r in ("first", "second"):
        pairs = [(hum[i]["label"], ai_pair(i)[0 if r == "first" else 1]["label"]) for i in ids]
        k3, po3 = kappa(pairs, ("yes", "no", "borderline"))
        print(f"   human vs {r} AI reader (yes/no/borderline): agreement {po3:.3f}, kappa {k3:.3f}")
# sentence overlap where both say yes
both = [i for i in sample if hum[i]["label"] == "yes" and ai_conf(i)]
withs = [i for i in both if hum[i].get("sentences")]
ov = 0
for i in withs:
    a, b = ai_pair(i); s_ai = set(a.get("sentences") or []) | set(b.get("sentences") or [])
    ov += bool(set(hum[i]["sentences"]) & s_ai)
print(f"sentences: of {len(both)} items labeled yes by the human and AI-confirmed, {len(withs)} have human sentence numbers; "
      f"in {ov} of them the human marked at least one sentence an AI reader marked")
print("human yes without sentence numbers:", [i for i in sample if hum[i]["label"] in ("yes", "borderline") and not hum[i].get("sentences")])

# planned sensitivity check: primary test (restriction, original vs neutral, confirmation request) on the human-checked subset
models = ("qwen3_8b", "gptoss_20b")
per = collections.defaultdict(lambda: collections.defaultdict(list))
for m in models:
    for l in open(f"{R}/test_replay_restr_{m}/replay.jsonl"):
        r = json.loads(l)
        if r.get("error") or r.get("run_error") or r["job_id"].startswith("replay-control"): continue
        per[r["source_job_id"]][r["arm"]].append(r)
f = lambda r: r["n_confirm_requests"] > 0
def test(ids, label):
    ks = [key[i]["job_id"] for i in ids if per[key[i]["job_id"]]["original"] and per[key[i]["job_id"]]["neutral"]]
    o = sum(sum(map(f, per[k]["original"])) for k in ks); no = sum(len(per[k]["original"]) for k in ks)
    a = sum(sum(map(f, per[k]["neutral"])) for k in ks); na = sum(len(per[k]["neutral"]) for k in ks)
    d = [sum(map(f, per[k]["original"])) / len(per[k]["original"]) - sum(map(f, per[k]["neutral"])) / len(per[k]["neutral"]) for k in ks]
    dn = sum(x > 1e-12 for x in d); up = sum(x < -1e-12 for x in d)
    print(f"   {label}: {len(ks)} sources; original {o}/{no} -> neutral {a}/{na}; down {dn} / up {up}; sign p={sign_p(dn, up):.3g}")
print("== sensitivity check (test plan): restriction sources in the human-checked subset")
vs = [i for i in sample if i.startswith("V")]
test([i for i in vs if hum[i]["label"] == "yes"], "human yes")
test([i for i in vs if hum[i]["label"] == "yes" and ai_conf(i)], "human yes and AI-confirmed")
test([i for i in vs if ai_conf(i)], "AI-confirmed (for comparison, same subset)")
if h2:
    ids = [i for i in sample if i in h2]
    k3, po3 = kappa([(hum[i]["label"], h2[i]["label"]) for i in ids], ("yes", "no", "borderline"))
    print(f"== human vs second human on {len(ids)} items: agreement {po3:.3f}, kappa {k3:.3f}")
