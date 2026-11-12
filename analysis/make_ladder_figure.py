"""Figure: the ladder of help (Table 1), from the five runs' stage files (E4B x3, Qwen3.5-4B, Gemma 4 E2B).
    python3 analysis/make_ladder_figure.py   (from paper_track/) -> figures/source_data/fig_ladder.csv, figures/fig_ladder.{png,svg}
Panel A: share of tries solved at each rung. Panel B: tasks solved in all three tries (of 77). Series differ by marker and are
labelled directly; Table 2 is the table view."""
import collections, csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_figures import BLUE, ORANGE, AQUA, INK, INK2, MUTED, SURFACE, grid, plt, ROOT
YELLOW, MAGENTA = "#eda100", "#e87ba4"   # categorical slots 4 and 5 (validated with slots 1-3, light surface)

D = os.path.join(ROOT, "data", "training")
RUNS = [("E4B, our scaffold, first run", "ladder_stages.csv", [("loc1", "e4b_loc_ctrl_v1"), ("loc1", "e4b_loc_hint_v1"), ("diff1", "e4b_diff_v1"),
         ("d2_e4b_diff_blocks_v1", "e4b_diff_blocks_v1"), ("d2_e4b_diff_apply_v2", "e4b_diff_apply_v2")], BLUE, "o"),
        ("E4B, our scaffold, replication", "ladder2_stages.csv", [("ladder2", b) for b in ("e4b_loc_ctrl_v1", "e4b_loc_hint_v1", "e4b_diff_v1",
         "e4b_diff_blocks_v1", "e4b_diff_apply_v2")], ORANGE, "s"),
        ("E4B, official loop", "ladder3_stages.csv", [("ladder3", b) for b in ("e4b_off_ctrl_v1", "e4b_off_loc_v1", "e4b_off_diff_v1",
         "e4b_off_edits_v1", "e4b_off_apply_v1")], AQUA, "^"),
        ("Qwen3.5-4B, official loop", "ladder5_stages.csv", [("ladder5", f"q4b_off_{b}_v1") for b in ("ctrl", "loc", "diff", "edits", "apply")],
         YELLOW, "D"),
        ("Gemma 4 E2B, official loop", "ladder8_stages.csv", [("ladder8", f"e2b_off_{b}_v1") for b in ("ctrl", "loc", "diff", "edits", "apply")],
         MAGENTA, "v")]
RUNGS = ["Nothing", "Reference\nlines", "Reference\npatch", "Edit\ncommands", "Apply\ntool"]
ids = set(open(os.path.join(ROOT, "data", "ladder_ids77.txt")).read().split())
out = []
for name, f, arms, _, _ in RUNS:
    rows = list(csv.DictReader(open(os.path.join(D, f))))
    for k, (run, arm) in enumerate(arms):
        by = collections.defaultdict(list)
        for r in rows:
            if r["run"] == run and r["arm"] == arm and r["task"] in ids:
                by[r["task"]].append(r["solved"] == "1")
        assert len(by) == 77, (name, arm, len(by))
        share = 100 * sum(sum(v) / len(v) for v in by.values()) / len(by)
        out.append({"run": name, "rung": k, "solved_pct": round(share, 1), "all3": sum(all(v) for v in by.values()),
                    "once": sum(any(v) for v in by.values())})
os.makedirs(os.path.join(ROOT, "figures", "source_data"), exist_ok=True)
with open(os.path.join(ROOT, "figures", "source_data", "fig_ladder.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)

fig, (a, b) = plt.subplots(1, 2, figsize=(10.4, 4.3), gridspec_kw={"wspace": 0.28})
for name, _, _, colour, marker in RUNS:
    pts = [r for r in out if r["run"] == name]
    for ax, key in ((a, "solved_pct"), (b, "all3")):
        ys = [r[key] for r in pts]
        ax.plot(range(5), ys, color=colour, linewidth=2, zorder=3)
        ax.plot(range(5), ys, linestyle="none", marker=marker, markersize=6.5, color=colour, markeredgecolor=SURFACE,
                markeredgewidth=1.2, zorder=4, label=name)
for ax in (a, b):
    ax.set_xticks(range(5), labels=RUNGS, fontsize=8); ax.set_xlim(-0.3, 4.75); grid(ax)
a.set_ylim(0, 100); a.set_ylabel("Tries solved (%)")
a.set_title("A. Tries solved, as more of the answer is given")
b.set_ylim(0, 77); b.set_ylabel("Tasks solved in all 3 tries (of 77)")
b.axhline(77, color=MUTED, linewidth=0.8, linestyle=(0, (3, 3)))
b.text(0, 73.5, "every task, every try", color=INK2, fontsize=8)
b.set_title("B. Tasks solved every time")
last = {r["run"]: r for r in out if r["rung"] == 4}
DY = {"E4B, our scaffold, first run": -9, "E4B, our scaffold, replication": 3, "E4B, official loop": -3, "Qwen3.5-4B, official loop": 3,
      "Gemma 4 E2B, official loop": -3}   # separate close end labels
for name, _, _, colour, _ in RUNS:
    a.annotate(f"{last[name]['solved_pct']:.0f}%", (4, last[name]["solved_pct"]), xytext=(7, DY[name]), textcoords="offset points", color=INK, fontsize=8)
    b.annotate(f"{last[name]['all3']}", (4, last[name]["all3"]), xytext=(7, DY[name]), textcoords="offset points", color=INK, fontsize=8)
h, l = a.get_legend_handles_labels()
fig.legend(h, l, loc="lower center", bbox_to_anchor=(0.5, -0.1), ncol=3, frameon=False, handlelength=1.6, fontsize=8)
for ext in ("png", "svg"):
    fig.savefig(os.path.join(ROOT, "figures", f"fig_ladder.{ext}"), dpi=300, bbox_inches="tight")
print("\n".join(str(r) for r in out))
