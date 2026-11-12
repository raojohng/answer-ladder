# %%
"""Answer Ladder on Kaggle Benchmarks: all five rungs of help, one notebook.

The competition's own harness (swegemma 0.2.11, official loop: run_command, read_file, edit_file, write_file, submit_patch;
official grader) runs each task in subprocess mode with the benchmark model behind Kaggle's model proxy. The task statement
carries each rung's added paragraph, byte-identical to the paper's official-loop runs. The five rungs run side by side;
the score is the mean share of tries resolved over the rungs, and report.json holds every rung, try and task.
Inputs (all public Kaggle datasets, read as plain files):
  jaejohn/answer-ladder         the benchmark: rung task files (tasks/official_loop/), task ids, agent prompt, apply tool
  jaejohn/answer-ladder-inputs  the competition's task snapshots, sandbox setup and task wheels (sha256 manifest)
  metric/gemma-4-developer-agent-wheelhouse   the competition's harness wheels
Set the model to evaluate in the last cell."""
import hashlib, importlib.metadata, json, os, shutil, subprocess, sys
from pathlib import Path

RUNGS = [('ctrl', 'no help'), ('loc', 'reference lines'), ('diff', 'reference patch'), ('edits', 'edit commands'),
         ('apply', 'apply tool')]
TRIES = 1                    # tries per task and rung (the paper's local runs used 3)
CONCURRENCY = 3              # sessions at a time per rung (15 in all)
BUDGET = dict(timeout_seconds=60, max_tool_calls=50, max_time_minutes=8, max_turns=100)   # the competition's budget

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
RELEASE = find('tasks/official_loop/tasks_e4b_off_ctrl_v1.jsonl').parents[2]   # the answer-ladder dataset
TASK_IDS = (RELEASE / 'tasks/ids_77.txt').read_text().split()                  # the 77 tasks, fixed before any run
if os.environ.get('ANSWER_LADDER_LIMIT'):                                      # local tests only
    TASK_IDS = TASK_IDS[:int(os.environ['ANSWER_LADDER_LIMIT'])]
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
# The apply rung alone gets the apply tool (`python3 -m apply_fix <task>`), as in the paper's runs: its wheels folder is
# the base set plus the tool's wheel, and only sandboxes that receive that folder see the tool (patched in below).
WHEELS_APPLY = ROOT / 'wheels_apply'
shutil.copytree(WHEELS, WHEELS_APPLY, dirs_exist_ok=True)
shutil.copyfile(RELEASE / 'apply_tool/swe_fixtool-1.0-py3-none-any.whl', WHEELS_APPLY / 'swe_fixtool-1.0-py3-none-any.whl')   # source: apply_tool/apply_fix.py

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
TASKDEPS_APPLY = ROOT / 'taskdeps_apply' / 'site-packages'
TASKDEPS_APPLY.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(WHEELS_APPLY / 'swe_fixtool-1.0-py3-none-any.whl') as z:
    z.extractall(TASKDEPS_APPLY)
print('task dependencies unpacked:', len(best), 'packages (+ apply tool for the apply rung)', flush=True)

# Task rows per rung: the released official-loop task files (the competition's rows, statement plus the rung's paragraph).
rows = {json.loads(l)['instance_id']: json.loads(l) for l in (INPUTS / 'tasks.jsonl').read_text().splitlines() if l.strip()}
TASKS = {}
for key, _ in RUNGS:
    released = {json.loads(l)['instance_id']: l for l in (RELEASE / f'tasks/official_loop/tasks_e4b_off_{key}_v1.jsonl').read_text().splitlines() if l.strip()}
    TASKS[key] = ROOT / f'tasks_{key}.jsonl'
    TASKS[key].write_text(''.join(released[i] + '\n' for i in TASK_IDS))
BUNDLE = ROOT / 'bundle'
(BUNDLE / 'prompts').mkdir(parents=True, exist_ok=True)
(BUNDLE / 'configs').mkdir(exist_ok=True)
shutil.copyfile(RELEASE / 'bundles/e4b_off_ctrl_v1/prompts/system.md', BUNDLE / 'prompts/system.md')   # the official-loop prompt
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
_copy_to = SubprocessManager.copy_to


def _copy_to_with_apply(self, sandbox_id, src, dst, *args, **kwargs):
    """Official copy_to; when the apply rung's wheels folder is copied in, that sandbox also gets the apply tool."""
    out = _copy_to(self, sandbox_id, src, dst, *args, **kwargs)
    if str(dst).startswith('/wheels') and Path(src).resolve() == WHEELS_APPLY.resolve():
        for sp in self._sandboxes[sandbox_id]['venv'].glob('lib/python*/site-packages'):
            pth = sp / '_host_env.pth'
            pth.write_text(f'{TASKDEPS_APPLY}\n' + (pth.read_text() if pth.exists() else ''))
    return out


SubprocessManager.copy_to = _copy_to_with_apply


class FixedPatchEvaluator(Evaluator):
    def __init__(self, config, patches):
        super().__init__(config)
        self.patches = patches

    async def _run_agent_sandbox(self, task, snapshot_path, task_index, total_tasks, **kwargs):
        return self.patches[task.instance_id], None, SessionTrace()


def config(out, key, registry=None):
    return EvalConfig(tasks_path=TASKS[key], snapshots_dir=INPUTS / 'snapshots', results_dir=out, submission_dir=BUNDLE,
                      models=registry or ModelRegistry(), sandbox='subprocess', wheels_dir=WHEELS_APPLY if key == 'apply' else WHEELS, task_ids=list(TASK_IDS),
                      image='swebench-sandbox:latest', concurrency=CONCURRENCY, display_mode='quiet',
                      verification_timeout_seconds=300, **BUDGET)


def results(out):
    return {r['instance_id']: r for r in map(json.loads, (out / 'task_results.jsonl').read_text().splitlines())}


async def rung(llm, key, report):
    out = {}
    for t in range(1, TRIES + 1):
        model, _ = make_model(llm, ROOT / f'model_calls_{key}.jsonl', record_sdk=False)
        registry = ModelRegistry()
        registry.register('kaggle_hosted_model', model)
        cfg = config(ROOT / f'run_{key}_t{t}', key, registry)
        cfg.generation_constraints = GenerationConstraints(allowed_fields=None, max_output_tokens=NumericRange(1, 32768), defaults={})
        await Evaluator(cfg).run()
        out[t] = results(ROOT / f'run_{key}_t{t}')
    solved = [bool(out[t].get(i, {}).get('resolved')) for t in out for i in TASK_IDS]   # a missing task counts as unsolved
    report['rungs'][key] = {'solved': sum(solved), 'tries': len(solved), 'share': sum(solved) / len(solved),
                            'missing': [(t, i) for t in out for i in TASK_IDS if i not in out[t]],
                            'errors': {f'{i} t{t}': r.get('error') for t in out for i, r in out[t].items() if r.get('error')},
                            'results': out}
    print(f"{key}: {sum(solved)} of {len(solved)} tries solved", flush=True)


async def ladder(llm, report):
    report['rungs'] = {}
    await asyncio.gather(*(rung(llm, key, report) for key, _ in RUNGS))
    report['model_calls'] = {k: len((ROOT / f'model_calls_{k}.jsonl').read_text().splitlines())
                             for k, _ in RUNGS if (ROOT / f'model_calls_{k}.jsonl').exists()}
    return sum(report['rungs'][k]['share'] for k, _ in RUNGS) / len(RUNGS)


@kbench.task(name='TASK_NAME')
def answer_ladder(llm) -> float:
    report = {'rungs_order': [k for k, _ in RUNGS], 'tries': TRIES, 'model': getattr(llm, 'model', None), 'tasks': len(TASK_IDS), 'budget': BUDGET, 'versions':
              {p: importlib.metadata.version(p) for p in ['swegemma', 'adk-submission', 'adk-eval-core', 'google-adk', 'litellm']}}
    score = 0.0
    if 'gemma' not in str(report['model']).lower():
        # Pushing a task starts a run on Kaggle's default model; this benchmark spends model budget on Gemma only.
        # AssertionError is kaggle-benchmarks' non-blocking failure: this run is marked failed, the notebook completes,
        # and the task stays runnable for Gemma models (any other exception fails task creation).
        raise AssertionError(f"Answer Ladder runs Gemma models only; {report['model']} skipped with no model calls.")
    try:
        job = ladder(llm, report)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            score = pool.submit(contextvars.copy_context().run, asyncio.run, job).result()
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
        report['traceback'] = traceback.format_exc()
    finally:
        report['score'] = score
        (ROOT / 'report.json').write_text(json.dumps(report, indent=1, default=str) + '\n')
        summary = {k: v for k, v in report.items() if k != 'rungs'}
        summary['rungs'] = {k: {x: y for x, y in r.items() if x != 'results'} for k, r in report.get('rungs', {}).items()}
        (ROOT / 'summary.json').write_text(json.dumps(summary, indent=1, default=str) + '\n')
        print('ANSWER_LADDER_REPORT', json.dumps(summary, default=str)[:6000], flush=True)
    if 'error' in report:
        raise RuntimeError(report['error'])
    return score


# %%
answer_ladder.run(kbench.llm)
