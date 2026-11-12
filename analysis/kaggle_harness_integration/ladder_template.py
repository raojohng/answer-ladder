# %%
"""Answer Ladder on Kaggle Benchmarks: RUNG_TITLE.

The competition's own harness (swegemma 0.2.11, official loop: run_command, read_file, edit_file, write_file, submit_patch;
official grader) runs each task in subprocess mode with the benchmark model behind Kaggle's model proxy. The task statement
carries the rung's added paragraph, byte-identical to the paper's official-loop runs. Score = share of tasks resolved.
Inputs: dataset jaejohn/answer-ladder-inputs (task snapshots, task rows, sandbox setup, task wheels; sha256 manifest) and
the competition's public wheelhouse (metric/gemma-4-developer-agent-wheelhouse) for the harness wheels."""
import base64, hashlib, importlib.metadata, json, lzma, os, shutil, subprocess, sys
from pathlib import Path

RUNG = 'RUNG_KEY'            # ctrl | loc | diff | edits | apply | calibration
TASK_IDS = TASK_IDS_LIST     # fixed list, chosen before any hosted run
CONCURRENCY = 4
BUDGET = dict(timeout_seconds=60, max_tool_calls=50, max_time_minutes=8, max_turns=100)   # the competition's budget
STATEMENTS_XZ = 'STATEMENTS_B64'
APPLY_WHEEL = 'APPLY_WHEEL_B64'

INPUT_ROOT = Path(os.environ.get('ANSWER_LADDER_INPUT_ROOT', '/kaggle/input'))   # overridable only for local tests
ROOT = Path(os.environ.get('ANSWER_LADDER_WORK', Path.cwd() / 'answer_ladder_run'))
ROOT.mkdir(exist_ok=True)


def find(pattern):
    """glob (not rglob) so symlinked mounts are followed."""
    for depth in range(1, 6):
        hits = sorted(INPUT_ROOT.glob('/'.join(['*'] * depth) + '/' + pattern))
        if hits:
            return hits[0]
    raise FileNotFoundError(pattern)


INPUTS = find('manifest.json').parent          # answer_ladder_inputs/
HARNESS = find('swegemma-0.2.11-py3-none-any.whl').parent
manifest = json.loads((INPUTS / 'manifest.json').read_text())


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


needed = ['tasks.jsonl', 'sandbox/setup.py'] + [f'snapshots/{i}.tgz' for i in TASK_IDS] + [k for k in manifest if k.startswith('wheels/')]
bad = [k for k in needed if sha(INPUTS / k) != manifest[k]]
assert not bad, f'manifest mismatch: {bad}'
print('inputs', INPUTS, '| harness wheels', HARNESS, '| verified', len(needed), 'files', flush=True)

# Writable copies of the small inputs (the mounts are read-only); snapshots are only read.
(ROOT / 'sandbox').mkdir(exist_ok=True)
shutil.copyfile(INPUTS / 'sandbox/setup.py', ROOT / 'sandbox/setup.py')   # contents only: mounts are read-only
WHEELS = ROOT / 'wheels'
WHEELS.mkdir(exist_ok=True)
for f in (INPUTS / 'wheels').glob('*.whl'):
    # The harness keeps only the highest version of each wheel; fastapi at these commits needs starlette<0.50.
    if f.name.startswith('starlette-') and tuple(int(x) for x in f.name.split('-')[1].split('.')[:2]) >= (0, 50):
        continue
    shutil.copyfile(f, WHEELS / f.name)
# Test-only dependencies missing from the public wheels (fastapi's tests import them): the same five wheels, by exact
# version and sha256, that the paper's runs added (RTX work/wheels_fastapi). Fetched from PyPI and checked.
EXTRA_WHEELS = {
    'inline_snapshot-0.36.1-py3-none-any.whl': '9d795198efcf956670a8ed588c85708dd3575a08341c63e2b34745a2ba0c6245',
    'dirty_equals-0.11-py3-none-any.whl': 'b1d7093273fc2f9be12f443a8ead954ef6daaf6746fd42ef3a5616433ee85286',
    'typing_inspection-0.4.4-py3-none-any.whl': '65b8397ba37ccbce054456aaccddfc91e6e3083c92824df348d96ca832f3f147',
    'asttokens-3.0.2-py3-none-any.whl': '9da13157f5b28becde0bd374fc677dcd3c290614264eff096f167c469cd9f933',
    'executing-2.3.0-py3-none-any.whl': '736e859c9f8701f11fcf516856f26f562e04776387824b43a35a1dfe21c84122',
}
import urllib.request
for wheel, digest in EXTRA_WHEELS.items():
    name, version = wheel.split('-')[:2]
    meta = json.load(urllib.request.urlopen(f'https://pypi.org/pypi/{name}/{version}/json', timeout=60))
    url = next(u['url'] for u in meta['urls'] if u['filename'] == wheel)
    data = urllib.request.urlopen(url, timeout=120).read()
    assert hashlib.sha256(data).hexdigest() == digest, f'sha256 mismatch: {wheel}'
    (WHEELS / wheel).write_bytes(data)
print('task wheels:', len(list(WHEELS.glob('*.whl'))), flush=True)
if RUNG == 'apply':
    # The harness unpacks small wheels from the task's wheels folder into the sandbox: `python3 -m apply_fix <task>`.
    (WHEELS / 'swe_fixtool-1.0-py3-none-any.whl').write_bytes(base64.b64decode(APPLY_WHEEL))

CONSTRAINTS = ROOT / 'constraints.txt'
CONSTRAINTS.write_text('protobuf==5.29.6\nhishel<2\n')   # kaggle-benchmarks 0.6.2 needs protobuf<6, breaks with hishel 2


def install(args):
    r = subprocess.run(['uv', 'pip', 'install', '--python', sys.executable, '-c', str(CONSTRAINTS)] + args,
                       capture_output=True, text=True, timeout=600)
    print(r.stdout[-1500:], r.stderr[-3000:], flush=True)
    if r.returncode:
        raise RuntimeError('Harness dependency installation failed')


install(['google-adk==1.36.1', 'google-genai==2.11.0', 'docker==7.1.0', 'litellm==1.104.2', 'networkx', 'numpy', 'pandas',
         'cachetools', 'python-dotenv', 'pyyaml', 'pytest==9.1.1', 'pytest-timeout==2.1.0', 'markdown-it-py==4.2.0', 'rich==15.0.0'])
install(['--no-deps'] + [str(HARNESS / w) for w in ('adk_eval_core-0.1.0-py3-none-any.whl',
         'adk_submission-0.2.13-py3-none-any.whl', 'swegemma-0.2.11-py3-none-any.whl')])

# Task dependencies. In Docker mode the harness unpacks the task wheels (highest version per package) into the sandbox's
# site-packages; in subprocess mode it installs nothing and the sandbox venv sees only the host's packages (which here
# include google-adk's newer starlette). Mirror Docker: unpack the same wheels, chosen for this interpreter, into one
# folder that each sandbox venv puts ahead of the host packages (patched in below). Grading is untouched.
import zipfile
from packaging.tags import sys_tags
from packaging.utils import parse_wheel_filename
SUPPORTED = set(sys_tags())
best = {}
for w in WHEELS.glob('*.whl'):
    name, version, _, tags = parse_wheel_filename(w.name)
    if set(tags) & SUPPORTED and (name not in best or version > best[name][0]):
        best[name] = (version, w)
TASKDEPS = ROOT / 'taskdeps' / 'site-packages'
TASKDEPS.mkdir(parents=True, exist_ok=True)
for _, w in sorted(best.values(), key=lambda x: x[1].name):
    with zipfile.ZipFile(w) as z:
        z.extractall(TASKDEPS)
print('task dependencies unpacked:', len(best), 'packages', flush=True)

# Task rows: the competition's rows for TASK_IDS, statement replaced by the rung's (calibration keeps the original).
rows = {json.loads(l)['instance_id']: json.loads(l) for l in (INPUTS / 'tasks.jsonl').read_text().splitlines() if l.strip()}
statements = json.loads(lzma.decompress(base64.b64decode(STATEMENTS_XZ))) if STATEMENTS_XZ else {}
TASKS = ROOT / f'tasks_{RUNG}.jsonl'
with TASKS.open('w') as out:
    for i in TASK_IDS:
        row = dict(rows[i])
        if statements:
            row['problem_statement'] = statements[i]
        out.write(json.dumps(row) + '\n')
BUNDLE = ROOT / 'bundle'
(BUNDLE / 'prompts').mkdir(parents=True, exist_ok=True)
(BUNDLE / 'configs').mkdir(exist_ok=True)
(BUNDLE / 'prompts/system.md').write_text(base64.b64decode('SYSTEM_PROMPT_B64').decode())
(BUNDLE / 'agent.yaml').write_text('name: swe_agent\nmodel: kaggle_hosted_model\ninstruction: !include prompts/system.md\n'
                                   'tools:\n  - run_command\n  - read_file\n  - edit_file\n  - write_file\n  - submit_patch\n'
                                   'generate_content_config: !include configs/sampling.yaml\n')
# Provider defaults: the proxy accepts no temperature/top_k, and thinking is the provider's own (not E4B's budget).
(BUNDLE / 'configs/sampling.yaml').write_text('max_output_tokens: 8192\n')
(BUNDLE / 'eval_config.yaml').write_text('evaluation:\n' + ''.join(f'  {k}: {v}\n' for k, v in BUDGET.items()))
os.environ['KAGGLE_SANDBOX_DIR'] = str(ROOT / 'sandbox')

# %%
# ADAPTER_SOURCE

# %%
import asyncio, concurrent.futures, contextvars, traceback
import kaggle_benchmarks as kbench
from adk_eval_core.tracing import SessionTrace
from adk_submission import GenerationConstraints, NumericRange
from adk_submission.registry import ModelRegistry
from swegemma.evaluate import EvalConfig, Evaluator
from swegemma.sandbox.subprocess import SubprocessManager

_start = SubprocessManager.start


def _start_with_taskdeps(self):
    """Official start(), then put the task dependencies first in the venv's host-packages .pth."""
    sandbox_id = _start(self)
    for sp in self._sandboxes[sandbox_id]['venv'].glob('lib/python*/site-packages'):
        pth = sp / '_host_env.pth'
        pth.write_text(f'{TASKDEPS}\n' + (pth.read_text() if pth.exists() else ''))
    return sandbox_id


SubprocessManager.start = _start_with_taskdeps


class FixedPatchEvaluator(Evaluator):
    def __init__(self, config, patches):
        super().__init__(config)
        self.patches = patches

    async def _run_agent_sandbox(self, task, snapshot_path, task_index, total_tasks, **kwargs):
        return self.patches[task.instance_id], None, SessionTrace()


def config(out, registry=None):
    return EvalConfig(tasks_path=TASKS, snapshots_dir=INPUTS / 'snapshots', results_dir=out, submission_dir=BUNDLE,
                      models=registry or ModelRegistry(), sandbox='subprocess', wheels_dir=WHEELS, task_ids=list(TASK_IDS),
                      image='swebench-sandbox:latest', concurrency=CONCURRENCY, display_mode='quiet',
                      verification_timeout_seconds=300, **BUDGET)


def results(out):
    return {r['instance_id']: r for r in map(json.loads, (out / 'task_results.jsonl').read_text().splitlines())}


async def calibrate(report):
    for name in ('empty', 'reference'):
        patches = {i: ('' if name == 'empty' else rows[i]['patch']) for i in TASK_IDS}
        await FixedPatchEvaluator(config(ROOT / f'calibration_{name}'), patches).run()
        report[name] = results(ROOT / f'calibration_{name}')
    report['valid'] = [i for i in TASK_IDS if not report['empty'][i]['resolved'] and report['reference'][i]['resolved']]
    return len(report['valid']) / len(TASK_IDS)


async def ladder(llm, report):
    model, _ = make_model(llm, ROOT / 'model_calls.jsonl', record_sdk=False)
    registry = ModelRegistry()
    registry.register('kaggle_hosted_model', model)
    cfg = config(ROOT / 'agent_run', registry)
    cfg.generation_constraints = GenerationConstraints(allowed_fields=None, max_output_tokens=NumericRange(1, 32768), defaults={})
    await Evaluator(cfg).run()
    res = results(ROOT / 'agent_run')
    report['results'] = res
    report['missing'] = [i for i in TASK_IDS if i not in res]
    report['errors'] = {i: r.get('error') for i, r in res.items() if r.get('error')}
    calls = ROOT / 'model_calls.jsonl'
    report['model_calls'] = len(calls.read_text().splitlines()) if calls.exists() else 0
    return sum(bool(res.get(i, {}).get('resolved')) for i in TASK_IDS) / len(TASK_IDS)   # a missing task counts as unsolved


@kbench.task(name='TASK_NAME')
def answer_ladder_rung(llm) -> float:
    report = {'rung': RUNG, 'model': getattr(llm, 'model', None), 'tasks': len(TASK_IDS), 'budget': BUDGET, 'versions':
              {p: importlib.metadata.version(p) for p in ['swegemma', 'adk-submission', 'adk-eval-core', 'google-adk', 'litellm']}}
    score = 0.0
    if RUNG != 'calibration' and 'gemma' not in str(report['model']).lower():
        # Pushing a task starts a run on Kaggle's default model; this benchmark spends model budget on Gemma only.
        # AssertionError is kaggle-benchmarks' non-blocking failure: this run is marked failed, the notebook completes,
        # and the task stays runnable for Gemma models (any other exception fails task creation).
        raise AssertionError(f"Answer Ladder runs Gemma models only; {report['model']} skipped with no model calls.")
    try:
        job = calibrate(report) if RUNG == 'calibration' else ladder(llm, report)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            score = pool.submit(contextvars.copy_context().run, asyncio.run, job).result()
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
        report['traceback'] = traceback.format_exc()
    finally:
        report['score'] = score
        (ROOT / 'report.json').write_text(json.dumps(report, indent=1, default=str) + '\n')
        print('ANSWER_LADDER_REPORT', json.dumps({k: v for k, v in report.items() if k not in ('results', 'empty', 'reference')},
              default=str)[:4000], flush=True)
    if 'error' in report:
        raise RuntimeError(report['error'])
    return score


# %%
answer_ladder_rung.run(kbench.llm)
