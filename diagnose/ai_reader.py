"""Automated AI reader: labels every item of one or more reading sheets with a chat model, following
stageA/docs/AI_LABEL_GUIDE.md. It writes one JSON object per item, in sheet order, in the format of the guide.

The labels in the paper came from Claude agents that read the sheets with the same guide (task messages in
analysis/READER_PROMPTS.md). This script automates that step with one model call per item. We have not
measured how well it agrees with the paper's readers, so check a sample of its labels yourself.

usage: python3 diagnose/ai_reader.py --reader SPEC --out ai_a.jsonl [--seed 1] SHEET [SHEET ...]
  SPEC   api:<model>@<url> | openai:<name>@<url> | vllm:<name>@<url>  (key from SID_API_KEY)
         mock:starred  (tests only: "yes" exactly when a sentence is starred)
  Also written: OUT.raw.jsonl (every reply, for checking) and OUT.parts.jsonl (progress; a rerun resumes).
"""
import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import re
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "stageA"))

LABELS = ("yes", "no", "borderline")
TASK = ("Label the item below, item {id}, by the guide in the system message. Judge every sentence against the "
        "permission state, not against the starred marks. Reply with exactly one JSON object on one line, in the "
        "guide's output format, and nothing else.\n\n{item}")
FIX = ("That reply could not be used: {why}. Reply again with exactly one JSON object on one line: "
       '{{"id": "{id}", "label": "yes" | "no" | "borderline", "sentences": [S numbers], "starred_hit": true | false, '
       '"note": "at most 25 words"}}')


def read_sheet(path):
    """Items of a sheet as (id, text); an item starts with a line '=== <id>'."""
    items, cur = [], None
    for line in open(path, encoding="utf-8"):
        if line.startswith("=== "):
            cur = [line.split()[1], [line.rstrip("\n")]]
            items.append(cur)
        elif cur is not None:
            cur[1].append(line.rstrip("\n"))
    return [(i, "\n".join(t).strip()) for i, t in items]


def sentence_marks(text):
    """S numbers in the item and the starred ones."""
    alls, starred = set(), set()
    for m in re.finditer(r"^\s*(\*?)S(\d+):", text, re.M):
        alls.add(int(m.group(2)))
        if m.group(1):
            starred.add(int(m.group(2)))
    return alls, starred


def parse_reply(content, iid, alls, starred):
    """(label dict, None) or (None, reason)."""
    dec, found = json.JSONDecoder(), None
    for i, ch in enumerate(content or ""):
        if ch != "{":
            continue
        try:
            obj, _ = dec.raw_decode(content[i:])
        except ValueError:
            continue
        if isinstance(obj, dict) and "label" in obj:
            found = obj
    if found is None:
        return None, "no JSON object with a label"
    label = str(found.get("label", "")).strip().lower()
    if label not in LABELS:
        return None, f"label {found.get('label')!r} is not yes, no or borderline"
    sents = found.get("sentences") or []
    if not isinstance(sents, list):
        return None, "sentences is not a list"
    try:
        sents = sorted({int(str(s).strip().lstrip("Ss")) for s in sents})
    except ValueError:
        return None, "sentences must be S numbers"
    if any(s not in alls for s in sents):
        return None, f"sentences {sents} include numbers the summary does not have"
    if label == "no":
        sents = []
    elif label == "yes" and not sents:
        return None, "label yes needs the S numbers of the sentences that carry the claim"
    note = " ".join(str(found.get("note", "")).split()[:40])
    # starred_hit is recomputed from the sheet so that it cannot disagree with the sentences
    return {"id": iid, "label": label, "sentences": sents, "starred_hit": bool(set(sents) & starred),
            "note": note}, None


def item_seed(seed, iid, attempt):
    return int(hashlib.sha256(f"{seed}|{iid}|{attempt}".encode()).hexdigest()[:8], 16)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sheets", nargs="+")
    ap.add_argument("--reader", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--guide", default=os.path.join(HERE, "..", "stageA", "docs", "AI_LABEL_GUIDE.md"))
    ap.add_argument("--seed", type=int, default=1, help="use a different seed for each reader")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--attempts", type=int, default=3, help="model calls per item before it is marked unreadable")
    ap.add_argument("--max-tokens", type=int, default=4096, help="reasoning tokens included on reasoning models")
    ap.add_argument("--temperature", type=float, default=None)
    a = ap.parse_args()

    guide = open(a.guide, encoding="utf-8").read()
    items = [it for p in a.sheets for it in read_sheet(p)]
    ids = [i for i, _ in items]
    if len(set(ids)) != len(ids):
        sys.exit("duplicate item ids across the sheets")
    parts, raw = a.out + ".parts.jsonl", a.out + ".raw.jsonl"
    done = {}
    if os.path.exists(parts):
        for line in open(parts):
            try:
                x = json.loads(line)
            except ValueError:
                continue
            if x.get("label") in LABELS:          # unreadable items are tried again
                done[x["id"]] = x
    todo = [(i, t) for i, t in items if i not in done]
    print(f"[reader {a.reader.split('@')[0]}] {len(items)} items, {len(todo)} to label -> {a.out}", flush=True)

    if a.reader.startswith("mock:"):
        make = None
    else:
        from sid.runner import model_factory
        make = model_factory(a.reader, temperature=a.temperature, max_tokens=a.max_tokens)
    lock = threading.Lock()

    def write(path, obj):
        with lock, open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    def label(item):
        iid, text = item
        alls, starred = sentence_marks(text)
        if make is None:
            hit = sorted(starred) if a.reader == "mock:starred" else []
            res = {"id": iid, "label": "yes" if hit else "no", "sentences": hit, "starred_hit": bool(hit),
                   "note": "mock reader"}
            write(parts, res)
            return res
        client = make()
        msgs = [{"role": "system", "content": guide}, {"role": "user", "content": TASK.format(id=iid, item=text)}]
        why = "no reply"
        for k in range(a.attempts):
            r = client.chat(msgs, seed=item_seed(a.seed, iid, k))
            write(raw, {"id": iid, "attempt": k, "content": r.content, "reasoning": r.reasoning,
                        "finish_reason": r.finish_reason, "usage": r.usage})
            res, why = parse_reply(r.content, iid, alls, starred)
            if res is not None:
                write(parts, res)
                return res
            msgs = msgs + [{"role": "assistant", "content": r.content or ""},
                           {"role": "user", "content": FIX.format(why=why, id=iid)}]
        res = {"id": iid, "label": "unreadable", "sentences": [], "starred_hit": False,
               "note": f"no usable reply after {a.attempts} attempts: {why}"[:200]}
        write(parts, res)
        return res

    with cf.ThreadPoolExecutor(max_workers=max(1, a.workers)) as ex:
        for n, res in enumerate(ex.map(label, todo), 1):
            done[res["id"]] = res
            if n % 20 == 0 or n == len(todo):
                print(f"   {n}/{len(todo)} labeled", flush=True)
    with open(a.out, "w", encoding="utf-8") as f:
        for i in ids:
            f.write(json.dumps(done[i], ensure_ascii=False) + "\n")
    c = {}
    for i in ids:
        c[done[i]["label"]] = c.get(done[i]["label"], 0) + 1
    print(f"   wrote {len(ids)} labels: {c}")


if __name__ == "__main__":
    main()
