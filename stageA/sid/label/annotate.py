"""Human annotation sheets and agreement.

export_sheet() writes one CSV per annotator with the same items in a
different random order. Items are blinded: no model name, arm, policy or
automatic label is shown. Annotators fill the `label` column with one of
judge.LABELS for each sentence, and `dropped_rules` per summary.

agreement() reads the filled sheets back and reports Cohen's kappa
(human vs human, and each human vs the judge / rule labeler) per category.
"""
from __future__ import annotations

import csv
import random
from collections import defaultdict

from ..metrics import cohen_kappa
from ..replay import sentences
from .judge import LABELS

FIELDS = ["item_id", "sentence_idx", "summary_context", "sentence", "user_request", "task_rules",
          "approval_events", "label", "copied", "notes"]


def export_sheet(items: list[dict], path_prefix: str, n_annotators: int = 2, seed: int = 0) -> list[str]:
    """items: [{"item_id", "summary", "user_request", "task_rules", "approval_events"}]."""
    rows = []
    for it in items:
        sents = sentences(it["summary"])
        for i, s in enumerate(sents):
            ctx = " ".join(sents[max(0, i - 1):i + 2])
            rows.append({"item_id": it["item_id"], "sentence_idx": i, "summary_context": ctx,
                         "sentence": s, "user_request": it["user_request"],
                         "task_rules": it["task_rules"], "approval_events": it["approval_events"],
                         "label": "", "copied": "", "notes": ""})
    paths = []
    for a in range(n_annotators):
        rr = rows[:]
        random.Random(f"{seed}:{a}").shuffle(rr)
        p = f"{path_prefix}_annotator{a + 1}.csv"
        with open(p, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(rr)
        paths.append(p)
    with open(f"{path_prefix}_LABELS.txt", "w") as f:
        f.write("Allowed labels: " + ", ".join(LABELS) + "\n")
    return paths


def read_sheet(path: str) -> dict:
    out = {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            lab = (r.get("label") or "").strip()
            if lab:
                out[(r["item_id"], int(r["sentence_idx"]))] = lab
    return out


def agreement(sheets: dict, auto: dict = None) -> dict:
    """sheets: {name: {(item, idx): label}}; auto: {name: {(item, idx): label}} (judge/rules).
    Returns pairwise kappa overall and per binary category."""
    sources = {**sheets, **(auto or {})}
    names = list(sources)
    res = defaultdict(dict)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = sources[names[i]], sources[names[j]]
            keys = sorted(set(a) & set(b))
            if not keys:
                continue
            pair = f"{names[i]}~{names[j]}"
            res[pair]["n"] = len(keys)
            res[pair]["kappa_all"] = cohen_kappa([a[k] for k in keys], [b[k] for k in keys])
            for lab in LABELS[1:]:
                xa = [a[k] == lab for k in keys]
                xb = [b[k] == lab for k in keys]
                if any(xa) or any(xb):
                    res[pair][f"kappa_{lab}"] = cohen_kappa(xa, xb)
    return dict(res)
