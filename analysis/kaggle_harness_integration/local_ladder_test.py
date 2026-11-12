"""Local test of a generated hosted_ladder/<task>.py before pushing: mirrors the two Kaggle datasets with symlinks to the local
competition data (plus a sha256 manifest), runs the task's setup cell as on Kaggle, then the task body with a scripted fake model
(OpenAI chat API): it runs `python3 -m apply_fix <id>` if the statement mentions it, else applies the reference patch, then
submits. Prints the report summary.
    <hosted-like python> -I local_ladder_test.py hosted_ladder/<task>.py <empty work dir> [--empty-submit]"""
import asyncio, base64, hashlib, json, os, re, sys
from pathlib import Path
from types import SimpleNamespace

from openai.types.chat import ChatCompletion

SRC, WORK = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
DATA = Path(__file__).resolve().parents[3] / 'data'
WHEELHOUSE = Path(__file__).resolve().parents[3] / 'wheelhouse'
fake = WORK / 'input'
inp = fake / 'datasets/jaejohn/answer-ladder-inputs/answer_ladder_inputs'
inp.mkdir(parents=True)
for name in ('snapshots', 'sandbox', 'wheels', 'tasks.jsonl'):
    (inp / name).symlink_to(DATA / name)
(fake / 'datasets/jaejohn/answer-ladder').symlink_to(Path(__file__).resolve().parents[2] / 'release/answer_ladder')
(fake / 'datasets/metric').mkdir(parents=True)
(fake / 'datasets/metric/gemma-4-developer-agent-wheelhouse').symlink_to(WHEELHOUSE)
source = SRC.read_text()
m = re.search(r'^TASK_IDS = (\[.*\])', source, re.M)
if m:
    ids = eval(m.group(1))
else:   # task list read from the release at run time: test on its first N tasks
    n = int(os.environ.setdefault('ANSWER_LADDER_LIMIT', '4'))
    ids = (Path(__file__).resolve().parents[2] / 'release/answer_ladder/tasks/ids_77.txt').read_text().split()[:n]
need = ['tasks.jsonl', 'sandbox/setup.py'] + [f'snapshots/{i}.tgz' for i in ids] + [f'wheels/{p.name}' for p in (DATA / 'wheels').glob('*.whl')]
manifest = {k: hashlib.sha256((inp / k).read_bytes()).hexdigest() for k in need}
# manifest.json must sit inside answer_ladder_inputs/ like on Kaggle; the folder holds symlinks, so write it beside them.
(inp / 'manifest.json').write_text(json.dumps(manifest))
os.environ['ANSWER_LADDER_INPUT_ROOT'] = str(fake)
os.environ['ANSWER_LADDER_WORK'] = str(WORK / 'run')

body = source.split('\n# %%\n')
setup, adapter, task = body[0], body[1], body[2]
glb = {'__name__': 'ladder_test'}
exec(compile(setup + adapter + task.split('@kbench.task')[0], str(SRC), 'exec'), glb)

rows = glb['rows']


def create(**request):
    msgs = request['messages']
    user = next(m['content'] for m in msgs if m['role'] == 'user')
    user = user if isinstance(user, str) else json.dumps(user)
    tid = next(i for i in ids if i in user or rows[i]['problem_statement'][:200] in user)
    n_assist = sum(m['role'] == 'assistant' for m in msgs)
    if '--empty-submit' in sys.argv:
        n_assist += 1
    if n_assist == 0:
        if 'apply_fix' in user or '--apply-always' in sys.argv:
            cmd = f'python3 -m apply_fix {tid}'
        else:
            patch = rows[tid]['patch'] if rows[tid]['patch'].endswith('\n') else rows[tid]['patch'] + '\n'
            cmd = f"echo {base64.b64encode(patch.encode()).decode()} | base64 -d | git apply"
        msg = {'role': 'assistant', 'tool_calls': [{'id': f'c1_{tid}', 'type': 'function',
               'function': {'name': 'run_command', 'arguments': json.dumps({'command': cmd})}}]}
    elif n_assist == 1:
        msg = {'role': 'assistant', 'tool_calls': [{'id': f'c2_{tid}', 'type': 'function',
               'function': {'name': 'submit_patch', 'arguments': '{}'}}]}
    else:
        msg = {'role': 'assistant', 'content': 'Done.'}
    return ChatCompletion.model_validate({'id': 'x', 'object': 'chat.completion', 'created': 0, 'model': 'fake',
        'choices': [{'index': 0, 'message': msg, 'finish_reason': 'tool_calls' if 'tool_calls' in msg else 'stop'}],
        'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}})


llm = SimpleNamespace(model='fake', support_temperature=False, client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
report = {}
job = glb['calibrate'](report) if glb.get('RUNG') == 'calibration' else glb['ladder'](llm, report)
score = asyncio.run(job)
print('SCORE', score)
summary = {k: v for k, v in report.items() if k not in ('results', 'empty', 'reference')}
if 'rungs' in report:
    summary['rungs'] = {k: (r['solved'], r['tries'], r['missing'], r['errors']) for k, r in report['rungs'].items()}
if 'results' in report:
    summary['per_task'] = {i: (r['resolved'], r.get('error')) for i, r in report['results'].items()}
if 'empty' in report:
    summary['per_task'] = {i: (report['empty'][i]['resolved'], report['reference'][i]['resolved']) for i in ids}
print(json.dumps(summary, default=str, indent=1))
