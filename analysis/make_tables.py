"""Step 2 of 3. data/sessions.csv -> every number in the paper.

Writes tables/*.csv, tables/tables.md, tables/key_numbers.json and the source data of each figure
(figures/source_data/*.csv). Standard library only.

Usage: python3 analysis/make_tables.py        (from paper_track/)
"""
import collections, csv, json, math, os, statistics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KS = [1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48]
PLACES = ["no patch", "another file", "right file, other lines", "gold lines, misses a gold file", "gold lines"]
GROUPS = [("Solved in 15% of tries or more", lambda q: q >= 0.15), ("Solved in under 15%", lambda q: 0 < q < 0.15),
          ("Never solved", lambda q: q == 0)]
BINS = [("Never", lambda q: q == 0), ("Under 5%", lambda q: 0 < q < 0.05), ("5 to 15%", lambda q: 0.05 <= q < 0.15),
        ("15 to 50%", lambda q: 0.15 <= q < 0.5), ("50 to 90%", lambda q: 0.5 <= q < 0.9), ("Over 90%", lambda q: q >= 0.9)]


def read(path):
    return list(csv.DictReader(open(os.path.join(ROOT, path))))


def write(path, header, rows):
    path = os.path.join(ROOT, path)
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def by_task(rows):
    per = collections.defaultdict(list)
    for r in rows:
        per[r["task"]].append(r)
    return per


def at_least_one(rows, k):
    """Expected number of tasks with a solve among k of their tries, averaged over all subsets of k tries."""
    total = 0.0
    for rs in by_task(rows).values():
        n, s = len(rs), sum(r["solved"] for r in rs)
        total += 1 - (math.comb(n - s, k) / math.comb(n, k) if n - s >= k else 0)
    return total


def md(header, rows):
    out = ["| " + " | ".join(map(str, header)) + " |", "|" + "---|" * len(header)]
    return "\n".join(out + ["| " + " | ".join(map(str, r)) + " |" for r in rows])


def main():
    rows = read("data/sessions.csv")
    for r in rows:
        r["solved"] = int(r["solved"]); r["try"] = int(r["try"])
        r["gold_files"] = int(r["gold_files"]); r["gold_hunks"] = int(r["gold_hunks"])
    arms = {a["arm"]: a for a in read("analysis/arms.csv")}
    per = by_task(rows)
    rate = {t: sum(r["solved"] for r in rs) / len(rs) for t, rs in per.items()}
    doc, key = [], {}
    key["sessions"] = len(rows); key["solves"] = sum(r["solved"] for r in rows); key["tasks"] = len(per)
    key["tries_per_task_min_max"] = [min(map(len, per.values())), max(map(len, per.values()))]
    key["median_seconds"] = statistics.median(float(r["seconds"]) for r in rows if r["seconds"])
    key["median_tool_calls"] = statistics.median(int(r["tool_calls"]) for r in rows if r["tool_calls"])

    # Table 1 and Fig. 1: tasks solved at least once in k tries
    single_untrained = [r for r in rows if r["arm"] in ("e4b_official_v1", "e4b_edit_fair_v1")]
    curves = [("All arms pooled", rows),
              ("Official loop, untrained", [r for r in rows if r["arm"] == "e4b_official_v1"]),
              ("v8 scaffold, untrained", [r for r in rows if r["arm"] == "e4b_edit_fair_v1"]),
              ("Both untrained single-agent arms", single_untrained),
              ("All other arms", [r for r in rows if r not in single_untrained and r["arm"] not in ("e4b_official_v1", "e4b_edit_fair_v1")])]
    t1, f1 = [], []
    for label, rs in curves:
        n = min(map(len, by_task(rs).values()))
        vals = {k: round(at_least_one(rs, k), 1) for k in range(1, n + 1)}
        t1.append([label, n] + [vals.get(k, "") for k in KS])
        f1 += [[label, k, v] for k, v in vals.items()]
    write("tables/table1_tries_curve.csv", ["arms", "tries_per_task_available"] + [f"k={k}" for k in KS], t1)
    write("figures/source_data/fig1.csv", ["arms", "k", "tasks_solved_at_least_once"], f1)
    doc += ["## Table 1. Tasks solved at least once in k tries (of 86)", md(["Arms", "Tries available"] + [f"k={k}" for k in KS], t1)]
    k18 = {label: round(at_least_one(rs, 18), 1) for label, rs in curves[3:]}
    key["tasks_at_18_tries"] = k18
    key["one_try_share_of_48_tries"] = round(at_least_one(rows, 1) / at_least_one(rows, 48), 3)

    # Table 2 and Fig. 2: per-task solve rates
    t2 = [[name, sum(1 for q in rate.values() if test(q))] for name, test in BINS]
    write("tables/table2_solve_rate_bins.csv", ["solve_rate", "tasks"], t2)
    doc += ["## Table 2. Tasks by solve rate", md(["Solve rate", "Tasks"], t2)]
    ranked = sorted(per, key=lambda t: (-rate[t], t))
    tasks_rows = []
    for t in ranked:
        rs = per[t]
        at = [r for r in rs if r["place"] == "gold lines"]
        tasks_rows.append([t, len(rs), sum(r["solved"] for r in rs), round(rate[t], 4), rs[0]["gold_files"], rs[0]["gold_hunks"],
                           len(at), sum(r["solved"] for r in at)])
    head = ["task", "tries", "solves", "solve_rate", "gold_files", "gold_hunks", "tries_reaching_gold_lines", "solved_at_gold_lines"]
    write("tables/per_task.csv", head, tasks_rows)
    write("figures/source_data/fig2.csv", head, tasks_rows)
    solves = sorted((sum(r["solved"] for r in rs) for rs in per.values()), reverse=True)
    key["solves_held_by_top_10_tasks"] = [sum(solves[:10]), sum(solves)]
    ever = [t for t in per if rate[t] > 0]; never = [t for t in per if rate[t] == 0]
    shape = lambda ts: {"tasks": len(ts), "single_file": sum(per[t][0]["gold_files"] == 1 for t in ts),
                        "one_file_one_hunk": sum(per[t][0]["gold_files"] == 1 and per[t][0]["gold_hunks"] == 1 for t in ts),
                        "fastapi": sum(t.startswith("fastapi") for t in ts), "rich": sum(t.startswith("rich") for t in ts)}
    key["solved_at_least_once"] = shape(ever); key["never_solved"] = shape(never)
    key["solved_at_least_3_times"] = sum(1 for rs in per.values() if sum(r["solved"] for r in rs) >= 3)

    # Table 3 and Fig. 3: solves per complete pass, by arm
    passes = collections.defaultdict(list)
    for r in rows:
        passes[(r["arm"], r["run"], r["try"])].append(r)
    f3, per_arm = [], collections.defaultdict(list)
    for (arm, run, t), rs in sorted(passes.items()):
        if len({r["task"] for r in rs}) != len(per):
            continue  # incomplete pass
        s, empty = sum(r["solved"] for r in rs), sum(r["place"] == "no patch" for r in rs)
        per_arm[arm].append(s)
        f3.append([arms[arm]["loop"], arms[arm]["label"], arms[arm]["trained"], arm, run, t, s, empty])
    write("figures/source_data/fig3.csv", ["loop", "label", "trained", "arm", "run", "try", "solves", "no_patch"], f3)
    t3 = []
    for arm, a in arms.items():
        v = per_arm.get(arm, [])
        if v:
            t3.append([a["loop"], a["label"], a["training_data"] or "-", len(v), f"{min(v)} to {max(v)}" if len(v) > 1 else v[0],
                       round(sum(v) / len(v), 1), round(statistics.stdev(v), 2) if len(v) > 2 else ""])
    write("tables/table3_solves_per_pass.csv", ["loop", "arm", "training_data", "passes", "solves_per_pass", "mean", "sd"], t3)
    doc += ["## Table 3. Solves per complete pass over the 86 tasks", md(["Loop", "Arm", "Training data", "Passes", "Solves per pass", "Mean", "SD"], t3)]
    key["untrained_sd"] = {a: round(statistics.stdev(per_arm[a]), 2) for a in ("e4b_official_v1", "e4b_edit_fair_v1")}

    # Table 4 and Fig. 4: where patches land
    t4, f4 = [], []
    for name, test in GROUPS:
        ts = [t for t in per if test(rate[t])]
        rs = [r for t in ts for r in per[t]]
        c = collections.Counter(r["place"] for r in rs)
        at = [r for r in rs if r["place"] == "gold lines"]
        t4.append([name, len(ts)] + [f"{c[p] / len(rs):.0%}" for p in PLACES] + [f"{sum(r['solved'] for r in at)} of {len(at)}"])
        f4 += [[name, len(ts), p, c[p], len(rs), round(c[p] / len(rs), 4), sum(r["solved"] for r in rs if r["place"] == p)] for p in PLACES]
    write("tables/table4_patch_placement.csv", ["task_group", "tasks"] + PLACES + ["solved_at_gold_lines"], t4)
    write("figures/source_data/fig4.csv", ["task_group", "tasks", "place", "tries", "group_tries", "share", "solved"], f4)
    doc += ["## Table 4. Where patches land", md(["Task group", "Tasks"] + PLACES + ["Solved at gold lines"], t4)]
    cond = sum(r["solved_at"] / r["at"] for r in ({"at": x[6], "solved_at": x[7]} for x in tasks_rows) if r["at"])
    key["expected_solves_if_every_try_reached_gold_lines"] = round(cond, 1)
    key["solved_tries_outside_gold_lines"] = sum(r["solved"] for r in rows if r["place"] != "gold lines")

    open(os.path.join(ROOT, "tables/tables.md"), "w").write("# Tables, generated by analysis/make_tables.py\n\n" + "\n\n".join(doc) + "\n")
    json.dump(key, open(os.path.join(ROOT, "tables/key_numbers.json"), "w"), indent=1)
    print(open(os.path.join(ROOT, "tables/tables.md")).read())
    print(json.dumps(key, indent=1))


if __name__ == "__main__":
    main()
