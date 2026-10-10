"""Prototype: Figure 2 drawn at final printed size (\\textwidth = 6.3 in), so font sizes are true pt."""
import json, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
B, OUT = json.load(open(sys.argv[1])), sys.argv[2]
FAM = sys.argv[3] if len(sys.argv) > 3 else "Liberation Sans"
FS = float(sys.argv[4]) if len(sys.argv) > 4 else 8.5
H = float(sys.argv[5]) if len(sys.argv) > 5 else 2.0
plt.rcParams.update({"font.family": FAM, "font.size": FS, "axes.linewidth": 0.8, "axes.spines.top": False,
                     "axes.spines.right": False, "legend.frameon": False, "pdf.fonttype": 42,
                     "xtick.major.width": 0.8, "ytick.major.width": 0.8, "xtick.major.size": 2.5, "ytick.major.size": 2.5})
ARMS = [("neutral", "neutral (target sentences → filler)", "#3775BA", "o"), ("CONTROL", "control edit", "#8C8C8C", "s"),
        ("claim_correct", "true permission written in", "#4E9F50", "D"), ("no_compaction", "full history", "#9A4D8E", "^")]
SETS = ["dev", "test", "F1", "F2"]; NAMES = {"dev": "Dev", "test": "Test", "F1": "F1", "F2": "F2"}
fig, axes = plt.subplots(1, 2, figsize=(float(sys.argv[6]) if len(sys.argv) > 6 else 7.0, H), gridspec_kw={"wspace": 0.28})
for ax, kind, title, xl in ((axes[0], "restr", "(a) Unsupported restrictions", "Drop in confirmation requests (pp)"),
                            (axes[1], "auth", "(b) Unsupported authorizations", "Drop in unauthorized actions (pp)")):
    yt, yl = [], []
    for j, s in enumerate(SETS):
        d = B[f"{s}/{kind}"]
        for i, (arm, lab, col, mk) in enumerate(ARMS):
            a = arm if arm != "CONTROL" else ("edit_control" if "edit_control" in d else "neutral_control")
            v = d[a]; y = -(j * (len(ARMS) + 1.2) + i)
            ax.errorbar(v["est"], y, xerr=[[v["est"] - v["lo"]], [v["hi"] - v["est"]]], fmt=mk, color=col, ms=3.6, lw=1.0, capsize=1.6,
                        capthick=0.8, label=lab if j == 0 else None, zorder=3)
        yt.append(-(j * (len(ARMS) + 1.2) + 1.5)); yl.append(f"{NAMES[s]} ({d['neutral']['n']})")
    ax.axvline(0, color="#333333", lw=0.8, zorder=2)
    ax.xaxis.grid(True, color="#E6E6E6", lw=0.6, zorder=0)
    ax.set_yticks(yt); ax.set_yticklabels(yl)
    ax.set_xlabel(xl, labelpad=2)
    ax.set_title(title, fontsize=FS, loc="left", pad=3)
h, l = axes[0].get_legend_handles_labels()
fig.legend(h, l, loc="lower center", ncol=4, bbox_to_anchor=(0.5, 0.97), fontsize=FS, handletextpad=0.3, columnspacing=1.2)
for ext in ("pdf", "png"):
    fig.savefig(f"{OUT}.{ext}", dpi=300, bbox_inches="tight", pad_inches=0.02)
print("saved")
