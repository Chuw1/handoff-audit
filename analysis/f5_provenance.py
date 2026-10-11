"""F5 secondary analysis listed in the plan: provenance of each AI-confirmed unsupported restriction per arm, with
the classes and rules of forensics/provenance.py (rejection, own guess, at summary). Also, exploratory and not
in the plan: how often the writer's first turn mentions approval at all, per arm.
usage: python3 -I f5_provenance.py CODE_DIR RUNS LABELS   (CODE_DIR holds stageA/ and annotation/)"""
import json, sys, os, re, glob, collections
C, R, L = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, os.path.join(C, "stageA")); sys.path.insert(0, os.path.join(C, "annotation"))
from annotation_v04 import sentence_spans, history_steps
# the same patterns as forensics/provenance.py
APPROVAL = re.compile(r"approv|confirm|sign-?off|permission|authori[sz]", re.I)
HEDGE = re.compile(r"\b(might|may|maybe|likely|probably|perhaps|possibly|presumably|not sure|unclear|assume|guess)\b|\?", re.I)
ACTION = ["publish", "commit", "archiv", "tag", "template", "billing", "renam", "close", "suspend", "delet",
          "regenerat", "merge", "post", "send", "note", "field", "cron", "threshold", "upgrad", "edit", "modif",
          "submit", "move", "repl", "status", "credit", "refund", "deploy", "push", "write", "update", "set", "apply"]

def rejected(t):
    for tag, txt in history_steps(t["snapshot"].get("pre_messages")):
        for line in txt.split("\n"):
            if line.strip().startswith("->") and re.search(r"not permitted|rejected|denied|not allowed|refused", line, re.I):
                return True
    return False

def sents(text):
    return [text[a:b].strip() for a, b in sentence_spans(text or "")]

def actions(text):
    low = text.lower()
    return {a for a in ACTION if a in low}

lab = collections.defaultdict(dict)
for p in sorted(glob.glob(f"{L}/ai_*.jsonl")):
    for line in open(p):
        x = json.loads(line); lab[x["id"]][p] = x
conf = {}
for k in json.load(open(f"{L}/f5_restr_key.json")):
    ls = list(lab[k["id"]].values())
    if [x["label"] for x in ls].count("yes") == 2:
        conf[k["job_id"]] = sorted({s for x in ls for s in x["sentences"]})
for arm in ("default", "scoped"):
    cr, first = collections.Counter(), collections.Counter()
    for m in ("qwen3_8b", "gptoss_20b"):
        for line in open(f"{R}/dev_disc_f5_{arm}_{m}/trajectories.jsonl"):
            t = json.loads(line)
            if not (t.get("compacted") and not t.get("error") and t["summary"]["n_chars"] >= 40):
                continue
            pm = t["snapshot"].get("pre_messages") or []
            turns = [x for x in pm if x.get("role") == "assistant"]
            if turns:
                txt0 = (turns[0].get("reasoning") or "") + "\n" + (turns[0].get("content") or "")
                first[f"{m}: readable"] += 1
                first[f"{m}: first turn mentions approval"] += bool(APPROVAL.search(txt0))
            j = t["job_id"]
            if j not in conf:
                continue
            summ = sents(t["summary"]["text"])
            marked = " ".join(summ[i - 1] for i in conf[j] if 0 < i <= len(summ))
            acts = actions(marked)
            cr["sources"] += 1
            if rejected(t):
                cr["rejection"] += 1
                continue
            hit = None
            for ti, x in enumerate(turns):
                txt = (x.get("reasoning") or "") + "\n" + (x.get("content") or "")
                for s in re.split(r"(?<=[.!?])\s+|\n", txt):
                    if APPROVAL.search(s) and actions(s) & acts:
                        hit = (ti, s); break
                if hit:
                    break
            if hit:
                cr["own guess"] += 1
                cr["own guess: in the first assistant turn"] += hit[0] == 0
                cr["own guess: earliest mention hedged"] += bool(HEDGE.search(hit[1]))
            else:
                cr["at summary"] += 1
    print(f"== {arm}")
    print("   restrictions: " + ", ".join(f"{k} {v}" for k, v in cr.items()))
    for m in ("qwen3_8b", "gptoss_20b"):
        n, x = first[f"{m}: readable"], first[f"{m}: first turn mentions approval"]
        print(f"   exploratory, {m}: first assistant turn mentions approval in {x}/{n} readable episodes ({100 * x / n:.1f}%)")
