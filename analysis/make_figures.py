"""Step 3 of 3. figures/source_data/*.csv -> figures/fig1..fig4 (.png at 300 dpi and .svg).

Every figure is drawn only from its source-data file. Identity is never carried by colour alone: series differ
by marker shape, fill or hatch, and are labelled directly. Colours: three categorical slots that pass a
colour-vision-deficiency check on all pairs, and one blue ramp for ordered categories.

Usage: python3 analysis/make_figures.py        (from paper_track/, after make_tables.py)
"""
import collections, csv, os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#2a78d6", "#104281"]  # light -> dark, one hue

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "text.color": INK, "axes.labelcolor": INK2,
    "axes.edgecolor": AXIS, "axes.linewidth": 0.8, "xtick.color": MUTED, "ytick.color": MUTED,
    "xtick.labelcolor": INK2, "ytick.labelcolor": INK2, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "axes.spines.top": False, "axes.spines.right": False, "svg.fonttype": "none",
    "legend.frameon": False, "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlelocation": "left",
})


def read(name):
    return list(csv.DictReader(open(os.path.join(ROOT, "figures", "source_data", name))))


def save(fig, name):
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(ROOT, "figures", f"{name}.{ext}"), dpi=300, bbox_inches="tight")
    plt.close(fig)


def grid(ax, axis="y"):
    ax.grid(axis=axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def fig1():
    rows = read("fig1.csv")
    series = [("All arms pooled", BLUE, "o", "All runs pooled (trained and untrained)"), ("v8 scaffold, untrained", ORANGE, "s", "Our scaffold, untrained"),
              ("Official loop, untrained", AQUA, "^", "Official loop, untrained")]
    fig, ax = plt.subplots(figsize=(6.6, 3.9))
    marks = {1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48}
    for name, colour, marker, label in series:
        pts = sorted((int(r["k"]), float(r["tasks_solved_at_least_once"])) for r in rows if r["arms"] == name)
        xs, ys = zip(*pts)
        ax.plot(xs, ys, color=colour, linewidth=2, zorder=3)
        mk = [(x, y) for x, y in pts if x in marks or x == xs[-1]]
        ax.plot(*zip(*mk), linestyle="none", marker=marker, markersize=6.5, color=colour, markeredgecolor=SURFACE,
                markeredgewidth=1.2, zorder=4, label=label)
    pooled = dict(sorted((int(r["k"]), float(r["tasks_solved_at_least_once"])) for r in rows if r["arms"] == "All arms pooled"))
    ax.annotate(f"1 try: {pooled[1]} tasks", (1, pooled[1]), xytext=(1.15, 3.2), color=INK, fontsize=9,
                arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.8))
    ax.annotate(f"48 tries: {pooled[48]} tasks", (48, pooled[48]), xytext=(15.5, 41.5), color=INK, fontsize=9,
                arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.8))
    ax.set_xscale("log")
    ax.set_xticks([1, 2, 4, 8, 16, 32, 48], labels=["1", "2", "4", "8", "16", "32", "48"])
    ax.minorticks_off()
    ax.set_xlim(0.9, 56); ax.set_ylim(0, 45)
    ax.set_xlabel("Tries per task (log scale)"); ax.set_ylabel("Tasks solved at least once (of 86)")
    ax.set_title("Tasks solved at least once keep rising with more tries")
    grid(ax)
    ax.legend(loc="lower right", handlelength=1.6)
    save(fig, "fig1_tries_curve")


def fig2():
    rows = read("fig2.csv")
    rate = [100 * float(r["solve_rate"]) for r in rows]
    multi = [int(r["gold_files"]) > 1 for r in rows]
    solved = [r for r in rows if float(r["solve_rate"]) > 0]
    n = len(solved)
    fig, ax = plt.subplots(figsize=(6.6, 3.6))
    for i, (q, m) in enumerate(zip(rate, multi)):
        if q == 0:
            continue
        ax.bar(i + 1, q, width=0.72, color=ORANGE if m else BLUE, hatch="////" if m else None, edgecolor=SURFACE, linewidth=0.6, zorder=3)
    never = [r for r in rows if float(r["solve_rate"]) == 0]
    nm = sum(int(r["gold_files"]) > 1 for r in never)
    ax.annotate("", xy=(n + 1, 6), xytext=(len(rows), 6), arrowprops=dict(arrowstyle="|-|", color=MUTED, linewidth=0.9, mutation_scale=3))
    ax.text((n + 1 + len(rows)) / 2, 9, f"{len(never)} tasks never solved in about 50 tries\n({len(never) - nm} single-file, {nm} multi-file)",
            ha="center", va="bottom", fontsize=9, color=INK)
    top10 = sum(int(r["solves"]) for r in rows[:10]); total = sum(int(r["solves"]) for r in rows)
    ax.annotate("", xy=(0.6, 104), xytext=(10.4, 104), arrowprops=dict(arrowstyle="|-|", color=MUTED, linewidth=0.9, mutation_scale=3), annotation_clip=False)
    ax.text(11.2, 104, f"10 tasks hold {top10 / total:.0%} of all solves", va="center", fontsize=9, color=INK)
    ax.set_xlim(0, len(rows) + 1); ax.set_ylim(0, 110)
    ax.set_yticks([0, 25, 50, 75, 100], labels=["0%", "25%", "50%", "75%", "100%"])
    ax.set_xticks([1, 10, 20, 30, n, 50, 60, 70, 86])
    ax.set_xlabel("Task, ranked by solve rate"); ax.set_ylabel("Tries that solved the task")
    ax.set_title("A few tasks are near-certain; most are coin flips or never solved")
    grid(ax)
    ax.legend(handles=[Patch(facecolor=BLUE, label="Single-file fix"), Patch(facecolor=ORANGE, hatch="////", edgecolor=SURFACE, label="Multi-file fix")],
              loc="center right", bbox_to_anchor=(1.0, 0.62))
    save(fig, "fig2_solve_rate_per_task")


def fig3():
    rows = read("fig3.csv")
    loops = ["Official", "v8 scaffold", "Solver + reviewer"]
    order = collections.OrderedDict()
    for r in rows:
        order.setdefault((r["loop"], r["label"], r["trained"]), []).append(int(r["solves"]))
    heights = [sum(1 for k in order if k[0] == lp) for lp in loops]
    fig, axes = plt.subplots(len(loops), 1, figsize=(6.6, 5.6), sharex=True, gridspec_kw={"height_ratios": heights, "hspace": 0.32})
    for ax, lp in zip(axes, loops):
        arms = [(k, v) for k, v in order.items() if k[0] == lp]
        arms.sort(key=lambda kv: kv[0][2])  # untrained first
        base = next(v for k, v in arms if k[2] == "0")
        ax.axvspan(min(base), max(base), color="#ecebe6", zorder=0, linewidth=0)
        ax.axvline(sum(base) / len(base), color=MUTED, linewidth=1, zorder=1)
        for y, ((_, label, trained), vals) in enumerate(arms):
            seen = collections.Counter()
            for v in sorted(vals):
                off = seen[v] * 0.2 - 0.2 * (vals.count(v) - 1) / 2
                seen[v] += 1
                ax.plot(v, y + off, marker="o", markersize=6.5, zorder=3, linestyle="none",
                        markerfacecolor=BLUE if trained == "1" else SURFACE, markeredgecolor=BLUE if trained == "0" else SURFACE,
                        markeredgewidth=1.6 if trained == "0" else 1.0)
        ax.set_yticks(range(len(arms)), labels=[k[1] for k, _ in arms])
        ax.set_ylim(len(arms) - 0.4, -0.6)
        ax.set_title({"v8 scaffold": "Our scaffold"}.get(lp, lp), fontsize=9)
        grid(ax, "x")
    axes[-1].set_xlabel("Tasks solved in one pass over the 86 tasks (each dot is one pass)")
    axes[0].set_xlim(3, 17)
    axes[0].legend(handles=[
        Line2D([], [], marker="o", linestyle="none", markerfacecolor=SURFACE, markeredgecolor=BLUE, markeredgewidth=1.6, markersize=6.5, label="Untrained"),
        Line2D([], [], marker="o", linestyle="none", markerfacecolor=BLUE, markeredgecolor=SURFACE, markersize=6.5, label="Trained adapter"),
        Patch(facecolor="#ecebe6", label="Range of untrained passes"),
        Line2D([], [], color=MUTED, linewidth=1, label="Untrained mean")],
        loc="lower left", bbox_to_anchor=(-0.02, 1.2), ncol=4, columnspacing=1.2, handletextpad=0.5, fontsize=8)
    fig.suptitle("No trained adapter's mean beats its untrained mean by two standard errors of the difference", x=0.125, y=1.03, ha="left", fontsize=10, fontweight="bold")
    save(fig, "fig3_solves_per_pass")


def fig4():
    rows = read("fig4.csv")
    places = ["no patch", "another file", "right file, other lines", "gold lines, misses a gold file", "gold lines"]
    names = {"no patch": "No patch", "another file": "Another file", "right file, other lines": "Right file, other lines",
             "gold lines, misses a gold file": "Gold lines in one file of several", "gold lines": "Reaches the gold lines"}
    groups = list(collections.OrderedDict((r["task_group"], int(r["tasks"])) for r in rows).items())
    fig, ax = plt.subplots(figsize=(6.6, 2.9))
    for y, (g, n) in enumerate(groups):
        left = 0.0
        for p, colour in zip(places, RAMP):
            r = next(x for x in rows if x["task_group"] == g and x["place"] == p)
            w = 100 * float(r["share"])
            ax.barh(y, w, left=left, height=0.56, color=colour, edgecolor=SURFACE, linewidth=1.6, zorder=3)
            if w >= 7:
                ax.text(left + w / 2, y, f"{w:.0f}%", ha="center", va="center", fontsize=8.5, color="#ffffff" if colour in RAMP[3:] else INK, zorder=4)
            left += w
        at = next(x for x in rows if x["task_group"] == g and x["place"] == "gold lines")
        ax.text(102, y, f"{int(at['solved'])} of {int(at['tries'])} solved\nonce there ({int(at['solved']) / int(at['tries']):.0%})", va="center", fontsize=8.5, color=INK)
    ax.set_yticks(range(len(groups)), labels=[f"{g}\n({n} tasks)" for g, n in groups])
    ax.set_ylim(len(groups) - 0.5, -0.5)
    ax.set_xlim(0, 100); ax.set_xticks([0, 25, 50, 75, 100], labels=["0%", "25%", "50%", "75%", "100%"])
    ax.set_xlabel("Share of tries, by where the submitted patch landed")
    ax.set_title("On often-solved tasks, a failed try is mostly a misplaced edit", pad=42)
    for s in ("left", "bottom"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
    ax.legend(handles=[Patch(facecolor=c, label=names[p]) for p, c in zip(places, RAMP)], loc="lower left", bbox_to_anchor=(-0.36, 1.0),
              ncol=3, fontsize=8, columnspacing=1.0, handlelength=1.2)
    save(fig, "fig4_patch_placement")


if __name__ == "__main__":
    fig1(); fig2(); fig3(); fig4()
    print("figures written to", os.path.join(ROOT, "figures"))
