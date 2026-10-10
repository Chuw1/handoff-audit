"""Exploratory (post hoc) provenance of AI-confirmed unsupported policy: where does each unsupported sentence
come from?  For every AI-confirmed source in Dev, Test, F2 and F4 it looks at the writer's context before
compaction (the snapshot's pre_messages: request, tool calls and results, the agent's own reasoning and text).

Restrictions, one class each, checked in this order:
  rejection    the pre-compaction history has a rejected or refused tool result (the paper's "overgeneralized")
  own guess    no rejection, but an earlier assistant turn pairs an approval word with an action word that also
               appears in a reader-marked sentence (e.g. "publishing likely needs approval")
  at summary   neither: the requirement first appears when the summary is written
Authorizations: whether an approval withdrawal was in the writer's context, whether a non-approver comment
was, and what the summary did with it.

usage: python3 -I provenance.py CODE_DIR DATA_DIR
"""
import json, sys, os, re, collections
C, D = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(C, "stageA")); sys.path.insert(0, os.path.join(C, "annotation"))
from annotation_v04 import sentence_spans, history_steps

APPROVAL = re.compile(r"approv|confirm|sign-?off|permission|authori[sz]", re.I)
HEDGE = re.compile(r"\b(might|may|maybe|likely|probably|perhaps|possibly|presumably|not sure|unclear|assume|guess)\b|\?", re.I)
ACTION = ["publish", "commit", "archiv", "tag", "template", "billing", "renam", "close", "suspend", "delet",
          "regenerat", "merge", "post", "send", "note", "field", "cron", "threshold", "upgrad", "edit", "modif",
          "submit", "move", "repl", "status", "credit", "refund", "deploy", "push", "write", "update", "set", "apply"]
WITHDRAW = re.compile(r"withdr[ae]w|revok|rescind|retract", re.I)

def both_yes(L, K):
    lab = collections.defaultdict(dict)
    for r in "abcd":
        p = f"{L}/ai_{r}.jsonl"
        if not os.path.exists(p): continue
        for l in open(p):
            x = json.loads(l); lab[x["id"]][r] = x
    out = {}
    for k in json.load(open(f"{L}/{K}")):
        ls = list(lab[k["id"]].values())
        if [x["label"] for x in ls].count("yes") == 2 and not k.get("control"):
            out[k["job_id"]] = sorted({s for x in ls for s in (x.get("sentences") or [])})
    return out

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

SETS = [
    ("Dev", f"{D}/ov310/labels", "restr_key.json", "auth_key.json", "ov310/raw/runs/disc_v039x_{m}", ("qwen3_8b", "gptoss_20b", "qwen3_14b")),
    ("Test", f"{D}/test310/labels", "test_restr_key.json", "test_auth_key.json", "test310/raw/runs/test_disc_v0310_{m}", ("qwen3_8b", "gptoss_20b")),
    ("F2", f"{D}/f1f2/labels", "f2_restr_key.json", "f2_auth_key.json", "f1f2/raw/runs/test_disc_f2_{m}", ("qwen3_8b", "gptoss_20b")),
    ("F4", f"{D}/f4/labels", "f4_restr_key.json", "f4_auth_key.json", "f4/raw/runs/test_disc_f4_{m}", ("qwen3_8b", "gptoss_20b")),
]
EX = collections.defaultdict(list)
for name, L, KR, KA, R, models in SETS:
    yr, ya = both_yes(L, KR), both_yes(L, KA)
    cr, ca = collections.Counter(), collections.Counter()
    for m in models:
        for l in open(f"{D}/{R.format(m=m)}/trajectories.jsonl"):
            t = json.loads(l)
            j = t.get("job_id")
            if j not in yr and j not in ya: continue
            pm = t["snapshot"].get("pre_messages") or []
            summ = sents(t["summary"]["text"])
            if j in yr:
                marked = " ".join(summ[i - 1] for i in yr[j] if 0 < i <= len(summ))
                acts = actions(marked)
                cr["sources"] += 1
                if rejected(t):
                    cls = "rejection"
                else:
                    first = None
                    turns = [x for x in pm if x.get("role") == "assistant"]
                    for ti, x in enumerate(turns):
                        txt = (x.get("reasoning") or "") + "\n" + (x.get("content") or "")
                        for s in re.split(r"(?<=[.!?])\s+|\n", txt):
                            if APPROVAL.search(s) and actions(s) & acts:
                                first = (ti, s.strip()); break
                        if first: break
                    if first:
                        cls = "own guess"
                        cr["own guess: in the first assistant turn"] += first[0] == 0
                        cr["own guess: earliest mention hedged"] += bool(HEDGE.search(first[1]))
                        cr["own guess: marked summary sentence hedged"] += bool(HEDGE.search(marked))
                        if len(EX[name]) < 3: EX[name].append((m, t["template_id"], first[1][:200], marked[:200]))
                    else:
                        cls = "at summary"
                        cr["at summary: writer's compaction reasoning has it"] += bool(APPROVAL.search(t["summary"].get("reasoning") or "") and actions(t["summary"].get("reasoning") or "") & acts)
                cr[cls] += 1
            if j in ya:
                ca["sources"] += 1
                tool_txt = " ".join(str(x.get("content", "")) for x in pm if x.get("role") == "tool")
                if "revoked" in t["template_id"] or WITHDRAW.search(tool_txt):
                    vis = bool(WITHDRAW.search(tool_txt))
                    ca["withdrawal in writer's context" if vis else "revoked template, withdrawal not in context"] += 1
                    if vis:
                        ca["  summary mentions the withdrawal"] += bool(WITHDRAW.search(t["summary"]["text"]))
                        ca["  writer's reasoning mentions it"] += bool(WITHDRAW.search(t["summary"].get("reasoning") or ""))
                elif t["meta"].get("external_suggestion"):
                    ca["non-approver comment in a tool result"] += 1
                else:
                    ca[f"other ({t['template_id'].split(':')[-1]})"] += 1
    print(f"== {name}")
    print("   restrictions: " + ", ".join(f"{k} {v}" for k, v in cr.items()))
    print("   authorizations: " + ", ".join(f"{k} {v}" for k, v in ca.items()))
print("\n== examples of 'own guess' (earliest assistant sentence | marked summary sentence)")
for name, xs in EX.items():
    for m, tid, g, s in xs:
        print(f"   {name} {m} {tid}\n      before: {g}\n      summary: {s}")
