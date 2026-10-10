"""Reader agreement, AI-confirmed sources (both readers "yes") and the replay target file, for one model.
The same rules as analysis/f3_targets.py (used in the paper), written so that an empty sheet or an
unreadable label does not stop the run: targets = the union of both readers' marked sentences
(1-based in the labels, 0-based in the target file); an item counts as confirmed only if both labels are "yes".

usage: python3 diagnose/targets.py LABELS_DIR TAG MODEL
  reads  LABELS_DIR/{TAG}_auth_key.json, {TAG}_restr_key.json, ai_a.jsonl, ai_b.jsonl
  writes LABELS_DIR/targets_{TAG}_{MODEL}.json and LABELS_DIR/agreement.json
"""
import collections
import hashlib
import json
import sys

L, TAG, MODEL = sys.argv[1], sys.argv[2], sys.argv[3]
CATS = ("yes", "no", "borderline", "unreadable")
KINDS = (("auth", "authorization", "invented_authorization"), ("restr", "restriction", "invented_restriction"))


def kappa(pairs, cats):
    n = len(pairs)
    if n == 0:
        return None, None
    po = sum(a == b for a, b in pairs) / n
    ca = collections.Counter(a for a, _ in pairs)
    cb = collections.Counter(b for _, b in pairs)
    pe = sum(ca[c] * cb[c] for c in cats) / n / n
    # with no variation (both readers used one and the same label throughout) kappa is undefined
    return ((po - pe) / (1 - pe) if pe < 1 else None), po


lab = {r: {} for r in "ab"}
for r in "ab":
    for line in open(f"{L}/ai_{r}.jsonl"):
        x = json.loads(line)
        lab[r][x["id"]] = x
targets, agree, skipped = {}, {}, []
for k, name, typ in KINDS:
    key = json.load(open(f"{L}/{TAG}_{k}_key.json"))
    pairs, conf = [], 0
    for it in key:
        la, lb = lab["a"].get(it["id"]), lab["b"].get(it["id"])
        if la is None or lb is None:
            sys.exit(f"item {it['id']} has no label from reader {'a' if la is None else 'b'}")
        pairs.append((la["label"], lb["label"]))
        if la["label"] == lb["label"] == "yes":
            tg = sorted({s - 1 for x in (la, lb) for s in x["sentences"]})
            if not tg:
                skipped.append(it["id"])
                continue
            conf += 1
            e = targets.setdefault(it["job_id"], {"items": [], "targets": [], "types": []})
            e["items"].append(it["id"])
            e["targets"] = sorted(set(e["targets"]) | set(tg))
            e["types"].append(typ)
    k3, po = kappa(pairs, CATS)
    k2, _ = kappa([(a == "yes", b == "yes") for a, b in pairs], (True, False))
    agree[name] = {"items": len(pairs), "confirmed": conf, "agreement": po, "kappa": k3, "kappa_yes_vs_not": k2,
                   "label_pairs": dict(collections.Counter("/".join(sorted(p)) for p in pairs)),
                   "unreadable_labels": sum(x == "unreadable" for p in pairs for x in p)}
    ks = ("n/a" if not pairs else "n/a (no variation)") if k3 is None else f"{k3:.2f}"
    print(f"{name}: {len(pairs)} items, {conf} AI-confirmed, reader kappa {ks}")
if skipped:
    print(f"   {len(skipped)} items labeled yes by both readers without sentence numbers were left out: {skipped}")
agree["left_out_without_sentences"] = skipped
p = f"{L}/targets_{TAG}_{MODEL}.json"
json.dump(targets, open(p, "w"), indent=1, sort_keys=True)
json.dump(agree, open(f"{L}/agreement.json", "w"), indent=1)
print(f"{len(targets)} sources -> {p} (sha256 {hashlib.sha256(open(p, 'rb').read()).hexdigest()[:12]})")
