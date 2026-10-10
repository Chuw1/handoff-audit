"""F2: agreement between AI readers, AI-confirmed sets (both 'yes'), and replay targets files.
Targets = union of both readers' marked sentences (1-based in labels -> 0-based indices)."""
import json, sys, collections, hashlib
L, OUT = sys.argv[1], sys.argv[2]
lab = {}
for r in "abcd":
    for l in open(f"{L}/ai_{r}.jsonl"):
        x = json.loads(l); lab.setdefault(x["id"], {})[r] = x
key = {}
for k in ("auth", "restr"):
    for x in json.load(open(f"{L}/f2_{k}_key.json")): key[x["id"]] = x
def kappa(pairs, cats=("yes", "no", "borderline")):
    n = len(pairs); po = sum(a == b for a, b in pairs) / n
    ca = collections.Counter(a for a, _ in pairs); cb = collections.Counter(b for _, b in pairs)
    pe = sum(ca[c] * cb[c] for c in cats) / n / n
    return (po - pe) / (1 - pe) if pe < 1 else 1.0, po
targets = {m: {} for m in ("qwen3_8b", "gptoss_20b")}
both = collections.defaultdict(list)
for pre, name in (("U", "authorization"), ("V", "restriction")):
    ids = sorted(i for i in lab if i.startswith(pre))
    pairs = [(lab[i].get("a", lab[i].get("c"))["label"], lab[i].get("b", lab[i].get("d"))["label"]) for i in ids]
    k3, po = kappa(pairs)
    yn = [(a == "yes", b == "yes") for a, b in pairs]
    k2, po2 = kappa([(str(a), str(b)) for a, b in yn], cats=("True", "False"))
    print(f"{name}: items {len(ids)}; agreement {po:.3f}, kappa(3 labels) {k3:.2f}; yes-vs-not kappa {k2:.2f}")
    print("   label pairs:", dict(collections.Counter(tuple(sorted(p)) for p in pairs)))
    for i in ids:
        ls = list(lab[i].values())
        if all(x["label"] == "yes" for x in ls):
            k = key[i]; m = k["model"]
            tg = sorted({s - 1 for x in ls for s in x["sentences"]})
            both[(name, m)].append(i)
            if k["job_id"] in targets[m]:
                e = targets[m][k["job_id"]]
                e["items"].append(i); e["targets"] = sorted(set(e["targets"]) | set(tg)); e["types"].append(k["types"][0])
            else:
                targets[m][k["job_id"]] = {"items": [i], "targets": tg, "types": list(k["types"])}
for (name, m), v in sorted(both.items()):
    print(f"AI-confirmed {name} {m}: {len(v)}")
for m, t in targets.items():
    multi = [v for v in t.values() if len(v["types"]) > 1]
    p = f"{OUT}/targets_f2_{m}.json"
    json.dump(t, open(p, "w"), indent=1, sort_keys=True)
    print(m, "sources", len(t), "both types", len(multi), "sha256", hashlib.sha256(open(p, "rb").read()).hexdigest())
