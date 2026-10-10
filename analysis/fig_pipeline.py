"""Figure 1 (study design). usage: python3 -I fig_pipeline.py OUTPREFIX [font family] [body, title, note font sizes] [height in]. Fonts are sized so that they print at about 7.5-8.5 pt at \textwidth; swatches use the fills and hatches of Figure 3."""
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
A = sys.argv[1:] + [None] * 6
OUT = A[0]
FAM = A[1] or "Liberation Sans"
FB, FT, FN = float(A[2] or 13.5), float(A[3] or 14.5), float(A[4] or 13)
H = float(A[5] or 3.55)
plt.rcParams.update({"font.family": FAM, "font.size": FB, "pdf.fonttype": 42, "hatch.linewidth": 1.0})
BLUE, BLUE2, RED1, RED, VIOLET = "#0F4D92", "#3775BA", "#F6CFCB", "#B64342", "#9A4D8E"
W = 10.9
fig = plt.figure(figsize=(W, H)); ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")
TOP, BOT = H - 0.08, 0.06
boxes = []
def box(x0, x1, title, body):
    ax.add_patch(FancyBboxPatch((x0, BOT), x1 - x0, TOP - BOT, boxstyle="round,pad=0.0,rounding_size=0.1", fc="white", ec=BLUE, lw=1.8))
    t = [ax.text(x0 + 0.12, TOP - 0.13, title, ha="left", va="top", fontsize=FT, weight="bold", color="#1A1A1A")]
    if body:
        t.append(ax.text(x0 + 0.12, TOP - 0.55, body, ha="left", va="top", fontsize=FB, color="#1A1A1A", linespacing=1.28))
    boxes.append((x0, x1, t))
def arrow(x0, x1, y=1.8):
    ax.add_patch(FancyArrowPatch((x0, y), (x1, y), arrowstyle="-|>", mutation_scale=14, lw=1.8, color="#444444"))
box(0.02, 2.22, "1 Task, ledger",
    "Request: publish\nthe release notes.\n\nLedger: publishing\nto release-notes is\nallowed, no approval\nneeded.\n\nEvent log: requests,\napprovals, revocations.")
arrow(2.25, 2.45)
box(2.48, 4.32, "2 Agent works",
    "Uses tools step\nby step.\n\nAsks for approval\nto publish to a\nwrong target; the\nsystem rejects\nthe request.")
arrow(4.35, 4.55)
box(4.58, 7.0, "3 Compaction",
    "History is dropped.\nThe successor gets\nonly the agent's\nown summary:")
ax.add_patch(FancyBboxPatch((4.7, 0.18), 2.18, 1.5, boxstyle="round,pad=0.0,rounding_size=0.07", fc=RED1, ec=RED, lw=1.4))
inner = [ax.text(4.8, 1.6, "“… Obtain explicit\napproval to publish\nthe release notes …”", ha="left", va="top", fontsize=FB, style="italic"),
         ax.text(4.8, 0.27, "Unsupported: the\nledger asks for no\napproval.", ha="left", va="bottom", fontsize=FN, color="#8E2F2E")]
arrow(7.03, 7.23)
box(7.26, 10.88, "4 Same-snapshot replay",
    "Restore the state at compaction;\nrun the successor 4 times per arm:")
arms = [("original summary", RED, None, "white"), ("neutral (target sentences → filler)", BLUE2, "..", "white"),
        ("control edit (other sentences)", "white", "///", "#A0A0A0"),
        ("true permission written in", "#4E9F50", "xx", "white"), ("full history, no summary", VIOLET, "\\\\\\\\", "white")]
lab = []
for i, (t, c, hatch, ec) in enumerate(arms):
    y = 2.3 - i * 0.36
    ax.add_patch(FancyBboxPatch((7.42, y - 0.11), 0.22, 0.22, boxstyle="round,pad=0.0,rounding_size=0.03", fc=c, ec=ec, hatch=hatch, lw=1.0))
    lab.append(ax.text(7.74, y, t, ha="left", va="center", fontsize=FB))
lab.append(ax.text(7.4, 0.16, "Outcome: asks for confirmation?\nActs without permission?", ha="left", va="bottom", fontsize=FN, color="#333333"))
fig.canvas.draw(); r = fig.canvas.get_renderer(); inv = ax.transData.inverted()
def ext(t):
    bb = t.get_window_extent(r); (a, b), (c, d) = inv.transform([[bb.x0, bb.y0], [bb.x1, bb.y1]]); return a, b, c, d
for x0, x1, ts in boxes:
    for t in ts:
        a, b, c, d = ext(t)
        if c > x1 - 0.05: print("OVERFLOW right", repr(t.get_text()[:30]), round(c, 2), ">", x1)
for t in inner:
    a, b, c, d = ext(t)
    if c > 4.7 + 2.18 - 0.04: print("OVERFLOW inner right", repr(t.get_text()[:25]), round(c, 2))
a, b, c, d = ext(inner[0]); a2, b2, c2, d2 = ext(inner[1])
if b < d2 + 0.05: print("OVERLAP inner texts", round(b, 2), round(d2, 2))
for t in lab:
    a, b, c, d = ext(t)
    if c > 10.88 - 0.05: print("OVERFLOW box4", repr(t.get_text()[:30]), round(c, 2))
# body text of box 3 vs red box top
a, b, c, d = ext(boxes[2][2][1]); print("box3 body bottom", round(b, 2), "red box top", 1.68)
a, b, c, d = ext(boxes[0][2][1]); print("box1 body bottom", round(b, 2))
a, b, c, d = ext(lab[-2]); a2, b2, c2, d2 = ext(lab[-1]); print("last arm bottom", round(b, 2), "outcome top", round(d2, 2))
a, b, c, d = ext(boxes[3][2][1]); print("box4 body bottom", round(b, 2), "first swatch top", 2.41)
fig.savefig(OUT + ".pdf", pad_inches=0.0)
fig.savefig(OUT + ".png", dpi=200, pad_inches=0.0)
sc = 453.0 / (W * 72)
print("scale %.3f -> body %.2fpt title %.2fpt note %.2fpt; printed height %.1fpt" % (sc, FB * sc, FT * sc, FN * sc, H * 72 * sc * 1.00375))
