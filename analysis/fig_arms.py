"""Figure 3: share of replay runs with the outcome, by arm and replay set (AI-confirmed sources only).
Style follows ChenLiu-1996/figures4papers (sans font, top/right spines off, frameless legend, pdf+png 300 dpi).
usage: python3 -I fig_arms.py allsets.json OUT_PREFIX"""
import json, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
D, OUT = json.load(open(sys.argv[1])), sys.argv[2]
plt.rcParams.update({"font.family": "Liberation Sans", "font.size": 16,
                     "axes.linewidth": 2, "axes.spines.top": False, "axes.spines.right": False,
                     "legend.frameon": False, "pdf.fonttype": 42, "ps.fonttype": 42, "hatch.linewidth": 1.2})
# Each arm also has its own fill pattern, so the bars can be told apart in grayscale (ACL formatting guidelines).
ARMS = [("original", "original summary", "#B64342", None),
        ("neutral", "neutral (target sentences → filler)", "#3775BA", ".."),
        ("CONTROL", "control edit (other sentences)", "#8C8C8C", "///"),
        ("claim_correct", "true permission written in", "#4E9F50", "xx"),
        ("no_compaction", "full history, no summary", "#9A4D8E", "\\\\")]
SETS = ["dev", "test", "F1", "F2"]
NAMES = {"dev": "Dev", "test": "Test", "F1": "F1", "F2": "F2"}
fig, axes = plt.subplots(1, 2, figsize=(12, 4.3), gridspec_kw={"wspace": 0.22})
for ax, kind, metric, ylab in ((axes[0], "restr", "confirm", "Asked for confirmation (% of runs)"),
                               (axes[1], "auth", "exec", "Unauthorized action (% of runs)")):
    w = 0.16
    for i, (arm, lab, col, hatch) in enumerate(ARMS):
        xs, ys = [], []
        for j, s in enumerate(SETS):
            d = D[f"{s}/{kind}"]
            a = arm if arm != "CONTROL" else ("edit_control" if "edit_control" in d else "neutral_control")
            num, den = d[a][metric][0], d[a][metric][1]
            xs.append(j + (i - 2) * w); ys.append(100 * num / den)
        if arm == "CONTROL":   # white bar, gray hatch
            ax.bar(xs, ys, width=w * 0.9, color="white", edgecolor=col, hatch=hatch, linewidth=1.5, label=lab, zorder=3)
        else:                  # colored bar, white hatch
            ax.bar(xs, ys, width=w * 0.9, color=col, edgecolor="white", hatch=hatch, linewidth=0.8, label=lab, zorder=3)
        for x, y in zip(xs, ys):          # a bar of height 0 is invisible: mark it so it is not read as missing
            if y == 0:
                ax.text(x, 0.6 if kind == "auth" else 1.2, "0", ha="center", va="bottom", fontsize=13, color="#333333")
    ax.set_xticks(range(len(SETS)))
    ax.set_xticklabels([f"{NAMES[s]}\n({D[f'{s}/{kind}']['sources']})" for s in SETS])
    ax.set_ylim(0, 100 if kind == "restr" else 50)
    ax.set_ylabel(ylab)
    ax.yaxis.grid(True, color="#E6E6E6", linewidth=1, zorder=0)
    ax.tick_params(width=2)
    ax.set_title("(a) Unsupported restrictions" if kind == "restr" else "(b) Unsupported authorizations", fontsize=16, loc="left")
h, l = axes[0].get_legend_handles_labels()
fig.legend(h, l, loc="lower center", ncol=3, bbox_to_anchor=(0.5, 0.98), fontsize=14, handlelength=1.4, columnspacing=1.2)
for ext in ("pdf", "png"):
    fig.savefig(f"{OUT}.{ext}", dpi=300, bbox_inches="tight", pad_inches=0.05)
print("saved", OUT)
