"""Proposed word cuts for paper_v11.md (draft; nothing is applied unless --apply). Each cut: (label, old text, new text).
    python3 -I analysis/v11_cuts.py paper_v11.md            # report words saved per cut and the total after all cuts
    python3 -I analysis/v11_cuts.py paper_v11.md --apply    # write the cut text back into the file"""
import sys

CUTS = [
("A1 abstract: graph sentence",
 "Offered the competition's code graph as tools, the agent used them in 18 of 231 tries, and told to use them it solved fewer; written into the task as five suggested symbols, the same data raised solves where it pointed to the right code and misled the first edit where it did not, with no net gain over two runs and none over a text-only hint.",
 "The competition's code graph, offered as tools, was used in 18 of 231 tries and cost solves when the agent was told to use it; written into the task, it helped where it pointed to the right code, misled where it did not, and did no better than a text-only hint."),
("A2 abstract: release sentence",
 "We release the ladder, with task files for both scaffolds, the apply tool, graph hints and 4,389 sessions, as a benchmark of whether an agent acts on what it is given.",
 "We release the ladder, its tools and sessions as a benchmark of whether an agent acts on what it is given."),
("I1 intro: contributions",
 """1. **A ladder of help** (Section 4): five interleaved conditions, from no hint to the answer with a one-call apply tool, replicated and repeated on the competition's official loop.
2. **Code graphs pushed and pulled** (Section 5): the competition's code graph and embeddings written into the task as a hint, against a text-only hint and the same data offered as tools.
3. **A released benchmark** (Section 8) of the ladder's tasks, tools, hints and sessions.
4. **Diagnosis** (Sections 6 and 7): failed tries without help, and what training changed.""",
 """1. **A ladder of help** (Section 4): five interleaved conditions, from no hint to the answer with an apply tool, on two scaffolds.
2. **Code graphs pushed and pulled** (Section 5): the competition's graph as a task hint, against a text-only hint and graph tools.
3. **A released benchmark** (Section 8).
4. **Diagnosis** (Sections 6 and 7): failed tries without help, and what training changed."""),
("S4a ladder: paired intervals condensed",
 "Paired over the 77 tasks (solves per pass, 95% task-bootstrap intervals), our scaffold's two runs agree: the location adds 8.0 (+3.0 to +13.3) in both, the patch 32.0 (+25.0 to +39.3) and 28.3 (+20.7 to +36.7) more, and the commands 11.7 (+4.3 to +19.3) and 14.3 (+7.3 to +21.7) more; the tool's further 3.7 and 4.0 are not distinguishable from zero (−1.7 to +9.0; −1.3 to +9.3). On the official loop the location adds 6.3 (+2.7 to +10.3) and the patch 40.0 more (+32.7 to +47.3), but neither the commands (−3.0; −9.7 to +3.7) nor the tool (+0.3 over the patch; −4.3 to +5.0) adds anything.",
 "Paired over the 77 tasks (solves per pass, 95% task-bootstrap intervals), our scaffold's two runs agree: the location adds 8.0 in both (lower bounds +3.0), the patch 32.0 and 28.3 more (+20.7 or more), the commands 11.7 and 14.3 more (+4.3 or more), and the tool's further 3.7 and 4.0 include zero. On the official loop the location adds 6.3 (+2.7 to +10.3) and the patch 40.0 (+32.7 to +47.3); the commands (−3.0) and the tool (+0.3 over the patch) add nothing."),
("S4b ladder: failure paragraph",
 "On our scaffold 100 and 93 tries never called the tool, though 148 of them passed by applying the patch by hand, and 52 called it without effect, 42 of them through the skill channel, where our scaffold had not installed it (a scaffold defect); on the official loop 72 of 231 tries called it, and 60 of the 159 that edited by hand failed.",
 "On our scaffold 193 tries never called the tool (148 passed by applying the patch by hand) and 52 called it without effect, 42 through a channel where our scaffold had not installed it (a scaffold defect); on the official loop 72 of 231 tries called it, and 60 of the 159 that edited by hand failed."),
("S5a graph: hint builder",
 "**Graph hint.** With no reference answer, we score each source node by TF-IDF between the task statement and its name and code, add 0.25 times the mean score of its callers and callees and 0.25 times its embedding similarity to the ten best text matches, and write the top five into the task as \"file: Class.method (defined at line n)\" under \"Where to look first (suggested by the repository's code graph; it may be wrong)\". Both weights were chosen on 52 other public tasks before any agent run. On the 77 tasks the five symbols cover the reference lines for 25 tasks and the reference file for 43; text alone gives 25 and 44, so graph and embeddings add little to retrieval itself.",
 "**Graph hint.** With no reference answer, we score each source node by TF-IDF against the task statement, add 0.25 times its neighbours' mean score and 0.25 times its embedding similarity to the ten best text matches (weights chosen on 52 other public tasks), and write the top five into the task as \"file: Class.method (defined at line n)\" under \"Where to look first (suggested by the repository's code graph; it may be wrong)\". They cover the reference lines for 25 of the 77 tasks and the reference file for 43; text alone gives 25 and 44."),
("S5b graph: drop the once/all-3 column of Table 2",
 """| Arm | Run | Solved | Once / all 3 | First applied edit on the reference lines | Solves per pass: hint covers the reference lines (25 tasks) / misses (52) |
|---|---|---|---|---|---|
| Control | 1 / 2 | 12.6 / 15.2% | 16/5, 21/4 | 39.4 / 36.0% | 5.0/4.7, 4.7/7.0 |
| Graph tools offered | 1 | 15.2% | 17 / 7 | 38.1% | 5.3 / 6.3 |
| Graph tools, told to use them | 2 | 9.5% | 16 / 2 | 36.8% | 4.0 / 3.3 |
| Graph hint in the task | 1 / 2 | 17.7 / 15.2% | 19/8, 17/6 | 35.9 / 37.7% | 8.3/5.3, 6.7/5.0 |
| Text-only hint | 2 | 13.4% | 15 / 6 | 36.8% | 6.3 / 4.0 |
| Reference lines | 1 | 20.8% | 21 / 11 | 77.1% | 7.7 / 8.3 |""",
 """| Arm | Run | Solved | First applied edit on the reference lines | Solves per pass: hint covers the reference lines (25 tasks) / misses (52) |
|---|---|---|---|---|
| Control | 1 / 2 | 12.6 / 15.2% | 39.4 / 36.0% | 5.0/4.7, 4.7/7.0 |
| Graph tools offered | 1 | 15.2% | 38.1% | 5.3/6.3 |
| Graph tools, told to use them | 2 | 9.5% | 36.8% | 4.0/3.3 |
| Graph hint in the task | 1 / 2 | 17.7 / 15.2% | 35.9 / 37.7% | 8.3/5.3, 6.7/5.0 |
| Text-only hint | 2 | 13.4% | 36.8% | 6.3/4.0 |
| Reference lines | 1 | 20.8% | 77.1% | 7.7/8.3 |"""),
("S5c graph: arms paragraph",
 "**Pushed against pulled.** Two interleaved runs on our scaffold compared arms (Table 2). Run 1: control; control with the three graph tools, which the harness then describes in the prompt; the graph hint; and the reference lines. Run 2: control; the graph hint again; a text-only hint (same builder and wording, both graph weights zero); and the graph tools with an instruction to use them.",
 "**Pushed against pulled.** Two interleaved runs on our scaffold (Table 2) compared control, the graph tools (which the harness then describes in the prompt), the hint and the reference lines; then control, the hint again, a text-only hint (both graph weights zero) and the tools with an instruction to use them."),
("S6 failed tries: annotation sentence",
 "Two language-model annotators, one of them the assistant that ran this study, labelled 20 such tasks from records that hid the verdict (agreement on 7 of 9 shared pairs needing judgement): failed tries changed the same function differently in 45% of pairs (27 to 64; 35% if a patch off the reference lines counts as a different location), and 9 of 11 failed tries without a patch end by claiming a fix never applied.",
 "Two language-model annotators, one the assistant that ran this study, labelled 20 such tasks with the verdict hidden (agreeing on 7 of 9 shared pairs needing judgement): failed tries changed the same function differently in 45% of pairs (27 to 64; 35% counting patches off the reference lines as elsewhere), and 9 of 11 failed tries without a patch claim a fix never applied."),
("S7a training: own successes",
 "**Imitating its own successes.** We imitated solved tries, cut at the first edit, tool-call tokens weighted four times; a control adapter on four tasks solved 74 of 80 free tries on them (untrained: 46). Frontier tasks were split at random: 100 trained, 60 held out; a second run trained on 283 tasks from both pools, every held-out repository among them. Against untrained tries from earlier runs (95% task-bootstrap intervals), the 100-task adapter solved 66.5% of tries on its trained tasks against 51.9% (+14.6; +7.1 to +22.1), but 49.6% against 46.9% on unseen tasks (+2.7; −3.7 to +8.9) and 9.3 against 10.2 official solves per pass; the 283-task adapter gave +1.9 (−4.5 to +8.5) unseen and +1.1 (−1.2 to +3.6) official.",
 "**Imitating its own successes.** We imitated solved tries cut at the first edit, tool-call tokens weighted four times (a control adapter on four tasks solved 74 of 80 tries on them; untrained 46). Trained on 100 random frontier tasks, with 60 held out, and compared with untrained tries from earlier runs (95% task-bootstrap intervals), the adapter solved 66.5% of tries on trained tasks against 51.9% (+14.6; +7.1 to +22.1), but 49.6% against 46.9% on unseen tasks (+2.7; −3.7 to +8.9) and 9.3 against 10.2 official solves per pass; an adapter on 283 tasks covering every held-out repository gave +1.9 (−4.5 to +8.5) unseen and +1.1 (−1.2 to +3.6) official."),
("S7b training: answer-given",
 "We gave 1,103 public tasks from the training and FreshSWE-Py sources (official repositories excluded) the fix as edit commands, kept one solved try for each of 400 tasks with the answer removed from its context, and trained on whole tries and on tool calls only. Both adapters collapsed: 2.0 and 1.3 official solves per pass against 10.2. In 358 rows the first action was the given edit, so the adapters learned to edit before reading: the whole-try adapter's first call was an edit in 235 of 256 tries (untrained: 1 of 749), and 12 of its 740 edits matched the file.",
 "We gave 1,103 training and FreshSWE-Py tasks the fix as edit commands, kept one solved try for each of 400 with the answer removed from its context, and trained on whole tries and on tool calls only. Both adapters collapsed (2.0 and 1.3 official solves per pass against 10.2): in 358 rows the first action was the given edit, so they learned to edit before reading; the whole-try adapter's first call was an edit in 235 of 256 tries (untrained: 1 of 749), and 12 of its 740 edits matched the file."),
("D discussion: last sentence",
 " Imitating answer-given tries is no shortcut: the demonstrations contain actions the student cannot justify without the answer.",
 ""),
("R related work: graph sentence",
 "Agentless [12] localizes in a fixed pipeline before editing; RepoGraph [13] and LocAgent [14] give larger models repository graphs as context or navigation tools; our graph arms compare these channels for a 4B agent.",
 "Agentless [12] localizes before editing; RepoGraph [13] and LocAgent [14] give larger models repository graphs as context or tools; we compare these channels for a 4B agent."),
]

path = sys.argv[1]
s = open(path).read()
before = len(s.split())
for label, old, new in CUTS:
    n = s.count(old)
    saved = len(old.split()) - len(new.split())
    print(f"{saved:4d}  {label}" + ("" if n == 1 else f"   !! found {n} times, skipped"))
    if n == 1:
        s = s.replace(old, new)
print(f"words {before} -> {len(s.split())} (wc -w style)")
if "--apply" in sys.argv:
    open(path, "w").write(s)
    print("APPLIED")
