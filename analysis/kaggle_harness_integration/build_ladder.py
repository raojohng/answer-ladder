"""Generate the six Kaggle Benchmarks task sources (calibration + five rungs) from ladder_template.py.
    python3 -I build_ladder.py [--ids N]     (N: first N of the fixed order; default all 77) -> hosted_ladder/<task>.py"""
import base64, json, lzma, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REL = HERE.parents[1] / 'release/answer_ladder'
RUNGS = [('calibration', 'answer-ladder-0-calibration', 'grader calibration (empty and reference patches, no model)'),
         ('ctrl', 'answer-ladder-1-no-help', 'rung 1, no help ("find this in the repository yourself")'),
         ('loc', 'answer-ladder-2-reference-lines', 'rung 2, the reference files and line ranges'),
         ('diff', 'answer-ladder-3-reference-patch', 'rung 3, the reference patch'),
         ('edits', 'answer-ladder-4-edit-commands', 'rung 4, the patch as ready-made edit_file commands'),
         ('apply', 'answer-ladder-5-apply-tool', 'rung 5, the patch with a one-call apply tool')]
ids = (REL / 'tasks/ids_77.txt').read_text().split()
if '--ids' in sys.argv:   # first N of a fixed interleaved order (rich and fastapi alternate), for cheap cost probes
    n = int(sys.argv[sys.argv.index('--ids') + 1])
    rich, fast = [i for i in ids if i.startswith('rich')], [i for i in ids if i.startswith('fastapi')]
    ids = [x for pair in zip(fast, rich) for x in pair][:n] if n < len(ids) else ids
template = (HERE / 'ladder_template.py').read_text().replace('# ADAPTER_SOURCE', (HERE / 'adapter.py').read_text())
prompt = (REL / 'bundles/e4b_off_ctrl_v1/prompts/system.md').read_bytes()
wheel = (REL / 'apply_tool/swe_fixtool-1.0-py3-none-any.whl').read_bytes()
out = HERE / 'hosted_ladder'
out.mkdir(exist_ok=True)
if '--all' in sys.argv:   # one task running all five rungs side by side; reads everything from public datasets (no embedded data)
    name = 'answer-ladder-all-rungs'
    src = (HERE / 'ladder_all_template.py').read_text().replace('# ADAPTER_SOURCE', (HERE / 'adapter.py').read_text()).replace('TASK_NAME', name)
    compile(src, name, 'exec')
    out.mkdir(exist_ok=True)
    (out / f'{name}.py').write_text(src)
    print(f'{name}.py  {len(src) / 1e3:.0f} kB, five rungs, tasks from tasks/ids_77.txt')
    sys.exit()
for key, name, title in RUNGS:
    stm = ''
    if key != 'calibration':
        rows = {json.loads(l)['instance_id']: json.loads(l)['problem_statement']
                for l in open(REL / f'tasks/official_loop/tasks_e4b_off_{key}_v1.jsonl')}
        stm = base64.b64encode(lzma.compress(json.dumps({i: rows[i] for i in ids}).encode(), preset=9)).decode()
    src = (template.replace('RUNG_TITLE', title).replace("'RUNG_KEY'", repr(key)).replace('TASK_IDS_LIST', repr(ids))
           .replace("'STATEMENTS_B64'", repr(stm)).replace('TASK_NAME', name)
           .replace("'APPLY_WHEEL_B64'", repr(base64.b64encode(wheel).decode() if key == 'apply' else ''))
           .replace('SYSTEM_PROMPT_B64', base64.b64encode(prompt).decode()))
    compile(src, name, 'exec')
    (out / f'{name}.py').write_text(src)
    print(f'{name}.py  {len(src) / 1e3:.0f} kB, {len(ids)} tasks')
