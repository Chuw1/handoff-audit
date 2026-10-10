"""Statistics used in Stage A (stdlib only).

- wilson(k, n): Wilson score interval for a proportion
- rule_of_three(n): 95% upper bound when 0 events are seen in n trials (3/n)
- cluster_bootstrap: CI for a statistic, resampling templates (clusters), not rows
- paired_arm_diff: paired difference between two replay arms on the same seeds
- exact_mcnemar: two-sided exact binomial test on discordant pairs
- source_level_diff: the same effect with the source summary as the unit (v0.3.7): per-source mean
  difference over its paired samples, mean over sources, cluster bootstrap over templates, sign test
- cohen_kappa: agreement between two raters
"""
from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from typing import Callable, Iterable


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float, float]:
    if n == 0:
        return (float("nan"),) * 3
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, centre - half), min(1.0, centre + half)


def rule_of_three(n: int) -> float:
    return 3.0 / n if n else float("nan")


def rate_with_ci(flags: list) -> dict:
    k, n = sum(bool(x) for x in flags), len(flags)
    p, lo, hi = wilson(k, n)
    out = {"k": k, "n": n, "rate": p, "wilson_lo": lo, "wilson_hi": hi}
    if k == 0 and n:
        out["upper95_rule_of_three"] = rule_of_three(n)
    return out


def cluster_bootstrap(rows: list[dict], cluster_key: str, stat: Callable[[list[dict]], float],
                      n_boot: int = 2000, seed: int = 0, alpha: float = 0.05) -> dict:
    """Percentile bootstrap that resamples whole clusters (e.g. templates)."""
    groups = defaultdict(list)
    for r in rows:
        groups[r[cluster_key]].append(r)
    keys = sorted(groups)
    if not keys:
        return {"est": float("nan"), "lo": float("nan"), "hi": float("nan"), "n_clusters": 0}
    est = stat(rows)
    rng = random.Random(seed)
    vals = []
    for _ in range(n_boot):
        sample = []
        for _k in keys:
            sample.extend(groups[rng.choice(keys)])
        v = stat(sample)
        if not math.isnan(v):
            vals.append(v)
    vals.sort()
    if not vals:
        return {"est": est, "lo": float("nan"), "hi": float("nan"), "n_clusters": len(keys)}
    lo = vals[int(alpha / 2 * len(vals))]
    hi = vals[min(len(vals) - 1, int((1 - alpha / 2) * len(vals)))]
    return {"est": est, "lo": lo, "hi": hi, "n_clusters": len(keys), "n_boot": len(vals)}


def mean_of(field: str) -> Callable[[list[dict]], float]:
    def f(rows):
        xs = [float(bool(r[field])) if isinstance(r[field], bool) else float(r[field]) for r in rows]
        return sum(xs) / len(xs) if xs else float("nan")
    return f


def exact_mcnemar(b: int, c: int) -> float:
    """Two-sided exact p-value for b vs c discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * p)


PAIR_KEYS = ("job_id", "source_job_id", "instance_id", "plant_kind", "sample", "successor")


def paired_arm_diff(rows: list[dict], arm_a: str, arm_b: str, outcome: str = "tempting_action_taken",
                    pair_keys=PAIR_KEYS, cluster_key: str = "template_id",
                    n_boot: int = 2000, seed: int = 0) -> dict:
    """Effect of arm_a vs arm_b on a binary outcome, paired on identical seeds."""
    idx = defaultdict(dict)
    for r in rows:
        key = tuple(r.get(k) for k in pair_keys)
        if r["arm"] in idx[key]:
            raise ValueError(f"two rows for arm {r['arm']} share pair key {key}; pairing is ambiguous")
        idx[key][r["arm"]] = r
    pairs = []
    for key, arms in idx.items():
        if arm_a in arms and arm_b in arms:
            a, b = bool(arms[arm_a][outcome]), bool(arms[arm_b][outcome])
            pairs.append({"a": a, "b": b, "d": int(a) - int(b),
                          cluster_key: arms[arm_a][cluster_key]})
    if not pairs:
        return {"n_pairs": 0}
    b_ = sum(1 for p in pairs if p["a"] and not p["b"])
    c_ = sum(1 for p in pairs if p["b"] and not p["a"])
    boot = cluster_bootstrap(pairs, cluster_key, mean_of("d"), n_boot=n_boot, seed=seed)
    return {"n_pairs": len(pairs), "rate_a": sum(p["a"] for p in pairs) / len(pairs),
            "rate_b": sum(p["b"] for p in pairs) / len(pairs), "diff": boot["est"],
            "diff_lo": boot["lo"], "diff_hi": boot["hi"], "n_clusters": boot["n_clusters"],
            "discordant_a_only": b_, "discordant_b_only": c_, "mcnemar_p": exact_mcnemar(b_, c_)}


def cohen_kappa(a: Iterable, b: Iterable) -> float:
    a, b = list(a), list(b)
    n = len(a)
    if n == 0 or n != len(b):
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb.get(k, 0) for k in ca) / (n * n)
    if pe == 1:
        return 1.0 if po == 1 else 0.0
    return (po - pe) / (1 - pe)


def threshold_at_fpr(neg_scores: list[float], target_fpr: float) -> float:
    """Smallest threshold t such that the fraction of negatives with score >= t is <= target_fpr."""
    if not neg_scores:
        return float("inf")
    s = sorted(neg_scores, reverse=True)
    allowed = int(math.floor(target_fpr * len(s)))
    if allowed >= len(s):
        return min(s)
    # flag score >= t; choose t just above the (allowed)-th highest negative
    return s[allowed] + 1e-9


def detection_stats(scores: list[float], labels: list[bool], thr: float) -> dict:
    tp = sum(1 for s, y in zip(scores, labels) if y and s >= thr)
    fp = sum(1 for s, y in zip(scores, labels) if not y and s >= thr)
    fn = sum(1 for s, y in zip(scores, labels) if y and s < thr)
    tn = sum(1 for s, y in zip(scores, labels) if not y and s < thr)
    rec = tp / (tp + fn) if tp + fn else float("nan")
    prec = tp / (tp + fp) if tp + fp else float("nan")
    fpr = fp / (fp + tn) if fp + tn else float("nan")
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "recall": rec, "precision": prec, "fpr": fpr,
            "recall_ci": wilson(tp, tp + fn)[1:] if tp + fn else None}


SOURCE_KEYS = ("job_id", "source_job_id", "instance_id", "plant_kind", "successor")   # PAIR_KEYS minus sample


def source_level_diff(rows: list[dict], arm_a: str, arm_b: str, outcome: str = "tempting_action_taken",
                      pair_keys=PAIR_KEYS, source_keys=SOURCE_KEYS, cluster_key: str = "template_id",
                      n_boot: int = 2000, seed: int = 0) -> dict:
    """Effect of arm_a vs arm_b with the source summary (one flagged or planted summary) as the unit.
    Repeated successor samples of one summary only reduce noise for that summary; they are not
    independent findings. For each source: the mean over its paired samples of (a - b). Then: the mean
    over sources, a percentile bootstrap that resamples templates (each with all its sources), and an
    exact two-sided sign test over sources (sources with a > b against sources with a < b)."""
    idx = defaultdict(dict)
    for r in rows:
        idx[tuple(r.get(k) for k in pair_keys)][r["arm"]] = r
    per = defaultdict(list)
    tpl = {}
    for arms in idx.values():
        if arm_a in arms and arm_b in arms:
            src = tuple(arms[arm_a].get(k) for k in source_keys)
            per[src].append(int(bool(arms[arm_a][outcome])) - int(bool(arms[arm_b][outcome])))
            tpl[src] = arms[arm_a][cluster_key]
    srcs = [{"source": s, "d": sum(v) / len(v), "n": len(v), cluster_key: tpl[s]} for s, v in per.items()]
    if not srcs:
        return {"n_sources": 0}
    boot = cluster_bootstrap(srcs, cluster_key, mean_of("d"), n_boot=n_boot, seed=seed)
    pos = sum(1 for x in srcs if x["d"] > 0)
    neg = sum(1 for x in srcs if x["d"] < 0)
    return {"n_sources": len(srcs), "n_templates": boot["n_clusters"], "n_pairs": sum(x["n"] for x in srcs),
            "diff": boot["est"], "diff_lo": boot["lo"], "diff_hi": boot["hi"],
            "sources_a_gt_b": pos, "sources_a_lt_b": neg, "sign_p": exact_mcnemar(pos, neg),
            "per_source": srcs}
