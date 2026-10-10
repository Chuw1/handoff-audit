"""Agreement between the two AI readers of each item: Cohen's kappa over yes/no/borderline, per set and kind.
Readers a and b read the same items, and so do readers c and d. usage: python3 -I agreement.py DATA_DIR"""
import json, sys, collections
S = sys.argv[1]
def kappa(pairs, cats=("yes", "no", "borderline")):
    n = len(pairs); po = sum(a == b for a, b in pairs) / n
    ca = collections.Counter(a for a, _ in pairs); cb = collections.Counter(b for _, b in pairs)
    pe = sum(ca[c] * cb[c] for c in cats) / n / n
    return (po - pe) / (1 - pe) if pe < 1 else 1.0, po
def labels(d, r):
    return {x["id"]: x["label"] for x in map(json.loads, open(f"{d}/ai_{r}.jsonl"))}
def report(name, d, keys, pairs=(("a", "b"), ("c", "d"))):
    L = {r: labels(d, r) for p in pairs for r in p}
    for kind, pre, keyfile in keys:
        ctrl = {k["id"] for k in json.load(open(f"{d}/{keyfile}")) if k.get("control")}
        for subset, keep in (("all items", lambda i: True), ("without unflagged controls", lambda i: i not in ctrl)):
            if subset != "all items" and not ctrl: continue
            pr = [(L[x][i], L[y][i]) for x, y in pairs for i in L[x] if i.startswith(pre) and i in L[y] and keep(i)]
            k, po = kappa(pr)
            print(f"{name:28s} {kind:13s} {subset:27s} items {len(pr):4d}  agreement {po:.3f}  kappa {k:.3f}")
report("Dev", f"{S}/ov310/labels", (("restriction", "V", "restr_key.json"), ("authorization", "U", "auth_key.json")))
report("Test", f"{S}/test310/labels", (("restriction", "V", "test_restr_key.json"), ("authorization", "U", "test_auth_key.json")))
report("F2", f"{S}/f1f2/labels", (("restriction", "V", "f2_restr_key.json"), ("authorization", "U", "f2_auth_key.json")))
report("compaction prompt, structured", f"{S}/h3/labels", (("restriction", "V", "h3s_restr_key.json"), ("authorization", "U", "h3s_auth_key.json")), (("a", "b"),))
report("compaction prompt, brief", f"{S}/h3/labels", (("restriction", "V", "h3b_restr_key.json"), ("authorization", "U", "h3b_auth_key.json")), (("c", "d"),))
report("F3 gpt-oss-120b", f"{S}/f3/labels", (("restriction", "V", "f3_restr_key.json"), ("authorization", "U", "f3_auth_key.json")))
report("F3c Qwen3-235B", f"{S}/f3c/labels", (("restriction", "V", "f3c_restr_key.json"), ("authorization", "U", "f3c_auth_key.json")))
