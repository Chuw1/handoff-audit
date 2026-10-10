"""Appendix table: AI-confirmed restriction sources by (set, model, template): sources, original, neutral, claim_correct.
usage: python3 -I tab_templates.py SCRATCH OUT.tex"""
import json, sys, collections
S, OUT = sys.argv[1], sys.argv[2]
M3 = ("qwen3_8b", "gptoss_20b", "qwen3_14b"); M2 = ("qwen3_8b", "gptoss_20b")
AB = {"qwen3_8b": "Q8", "gptoss_20b": "G20", "qwen3_14b": "Q14"}
def both_yes(L, K):
    lab = collections.defaultdict(list)
    for r in "abcd":
        for l in open(f"{L}/ai_{r}.jsonl"):
            x = json.loads(l); lab[x["id"]].append(x["label"])
    return {k["job_id"]: k["model"] for k in json.load(open(K)) if lab[k["id"]].count("yes") == 2 and not k.get("control")}
SETS = [("Dev", f"{S}/ov310/labels", f"{S}/ov310/labels/restr_key.json", [f"{S}/ov310/raw/runs/replay_v039x_restr_{m}/replay.jsonl" for m in M3]),
        ("Test", f"{S}/test310/labels", f"{S}/test310/labels/test_restr_key.json", [f"{S}/test310/raw/runs/test_replay_restr_{m}/replay.jsonl" for m in M2]),
        ("F1", f"{S}/test310/labels", f"{S}/test310/labels/test_restr_key.json", [f"{S}/f1f2/raw/runs/test_replay_f1_{m}/replay.jsonl" for m in M2]),
        ("F2", f"{S}/f1f2/labels", f"{S}/f1f2/labels/f2_restr_key.json", [f"{S}/f2r2/raw/runs/test_replay_f2_{m}/replay.jsonl" for m in M2])]
C = lambda r: r["n_confirm_requests"] > 0
rows = []
for name, L, K, paths in SETS:
    yes = both_yes(L, K)
    cell = collections.defaultdict(lambda: collections.Counter()); src = collections.defaultdict(set)
    for p in paths:
        for l in open(p):
            r = json.loads(l)
            if r.get("error") or r["source_job_id"] not in yes or r["job_id"].startswith("replay-control"): continue
            key = (yes[r["source_job_id"]], r["template_id"].split(":")[-1])
            src[key].add(r["source_job_id"])
            if r["arm"] in ("original", "neutral", "claim_correct"):
                cell[key][r["arm"]] += C(r); cell[key][r["arm"] + "_n"] += 1
    for key in sorted(cell, key=lambda k: (M3.index(k[0]), k[1])):
        c = cell[key]; n = c["original_n"]
        rows.append(f"{name} & {AB[key[0]]} & {key[1].replace('_', chr(92) + '_')} & {len(src[key])} & {c['original']}/{n} & {c['neutral']}/{n} & {c['claim_correct']}/{n} \\\\")
half = (len(rows) + 1) // 2
def block(rs):
    return ("\\begin{tabular}{lllrrrr}\n\\toprule\nSet & M. & Template & Src. & orig. & neutral & true p. \\\\\n\\midrule\n" + "\n".join(rs) + "\n\\bottomrule\n\\end{tabular}")
tex = ("\\begin{table*}[t]\n\\centering\n\\scriptsize\n\\setlength{\\tabcolsep}{3pt}\n" + block(rows[:half]) + "\\hfill\n" + block(rows[half:]) +
       "\n\\caption{AI-confirmed unsupported restrictions by set, model (Q8: Qwen3-8B, G20: gpt-oss-20b, Q14: Qwen3-14B) and template. "
       "Cells: runs with a confirmation request / runs. True p.: claim\\_correct.}\n\\label{tab:templates}\n\\end{table*}\n")
open(OUT, "w").write(tex)
print(len(rows), "rows")
