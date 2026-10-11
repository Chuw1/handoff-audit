"""F5 reader agreement: Cohen's kappa over yes/no/borderline between the two readers of each item, per kind
(U = authorization, V = restriction), as reported in Appendix H.
usage: python3 -I f5_agreement.py LABELS   (LABELS/ai_[a-f].jsonl; every item has exactly two labels)"""
import json, sys, glob, collections
L = sys.argv[1]
lab = collections.defaultdict(list)
for p in sorted(glob.glob(f"{L}/ai_*.jsonl")):
    for line in open(p):
        x = json.loads(line); lab[x["id"]].append(x["label"])
assert all(len(v) == 2 for v in lab.values()), "every item needs two labels"
def kappa(pairs, cats=("yes", "no", "borderline")):
    n = len(pairs); po = sum(a == b for a, b in pairs) / n
    ca = collections.Counter(a for a, _ in pairs); cb = collections.Counter(b for _, b in pairs)
    pe = sum(ca[c] * cb[c] for c in cats) / n / n
    return (po - pe) / (1 - pe), po
for pre, name in (("U", "authorization"), ("V", "restriction")):
    pairs = [tuple(v) for k, v in sorted(lab.items()) if k.startswith(pre)]
    k, po = kappa(pairs)
    pc = collections.Counter("/".join(sorted(p)) for p in pairs)
    print(f"{name}: items {len(pairs)}; agreement {po:.3f}, kappa(3 labels) {k:.2f}; label pairs {dict(sorted(pc.items()))}")
