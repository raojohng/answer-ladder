"""Where solved and failed tries diverge (Section 4): python3 analysis/stage_tables.py   (needs only data/stages_*.csv)
Tries of the v8 scaffold, single-file reference patches, sessions killed by the harness's compaction crash left out."""
import collections, csv, statistics

V8 = {"", "e4b_edit_fair_v1", "e4b_v8con_v1", "e4b_v8con2_v1", "e4b_r2d_v8_v1", "e4b_place1a_v1", "e4b_place1b_v1"}
def rows(name): return [r for r in csv.DictReader(open(f"data/{name}")) if r["crash"] == "0" and r["gold_files"] == "1" and r["arm"] in V8]
def before(r, key): return r[key] != "" and (r["i_first_applied"] == "" or int(r[key]) < int(r["i_first_applied"]))
def pct(rs, f): return f"{sum(f(r) for r in rs) / max(1, len(rs)):.0%}"
solved = lambda r: r["solved"] == "1"
final = lambda r: r["place"] == "gold lines"

def table(rs, label):
    n = len(rs)
    print(f"\n{label}: {n} tries on {len({r['task'] for r in rs})} tasks, solved {pct(rs, solved)}, median call of the first applied edit "
          f"{statistics.median(int(r['i_first_applied']) for r in rs if r['i_first_applied'])}, median calls {statistics.median(int(r['calls']) for r in rs)}")
    groups = (("first applied edit on the reference lines", [r for r in rs if r["first_applied_gold_lines"] == "1"]),
              ("first applied edit elsewhere", [r for r in rs if r["first_applied_gold_lines"] == "0"]),
              ("no edit applied", [r for r in rs if r["i_first_applied"] == ""]))
    for name, g in groups:
        print(f"  {name}: {len(g)} ({len(g)/n:.0%}) | final patch on the reference lines {pct(g, final)} | solved {pct(g, solved)}")
    edited = [r for r in rs if r["i_first_applied"] != ""]
    for name, g in (("read the reference lines before the first edit", [r for r in edited if before(r, "i_gold_read")]),
                    ("did not", [r for r in edited if not before(r, "i_gold_read")])):
        print(f"  {name}: {len(g)} | first edit on the reference lines {pct(g, lambda r: r['first_applied_gold_lines'] == '1')} | solved {pct(g, solved)}")
    print(f"  reference file named in a command or result before the first edit: {pct(rs, lambda r: before(r, 'i_gold_file_seen'))}; "
          f"reference lines read before it: {pct(rs, lambda r: before(r, 'i_gold_read'))}")
    print(f"  an edit hit the reference lines but the final patch is elsewhere: {pct(rs, lambda r: r['ever_gold_edit'] == '1' and not final(r))}")
    tasks = collections.defaultdict(list)
    for r in rs: tasks[r["task"]].append(r)
    mixed = [v for v in tasks.values() if 0 < sum(map(solved, v)) < len(v)]
    so = [r for v in mixed for r in v if solved(r)]; fa = [r for v in mixed for r in v if not solved(r)]
    f = lambda r: r["first_applied_gold_lines"] == "1"
    print(f"  within {len(mixed)} tasks with solved and failed tries: first edit on the reference lines in {pct(so, f)} of {len(so)} solved tries, {pct(fa, f)} of {len(fa)} failed")

train = [r for r in rows("stages_all.csv") if r["run"] in ("v8_sweep", "fresh_v8_p1")]
table(train, "Training and FreshSWE-Py tasks, untrained v8 scaffold")
official = rows("stages_official.csv")
table([r for r in official if r["arm"] == "e4b_edit_fair_v1"], "Official tasks, untrained v8 scaffold")
table(official, "Official tasks, all v8-scaffold arms")
