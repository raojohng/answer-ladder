# %%
"""Private official-harness integration check, separate from paper results."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT = Path.cwd() / 'official_harness_probe'
ROOT.mkdir(exist_ok=True)
INPUTS = ROOT / 'harness_inputs'
# The dataset may hold the packed archive or (uploaded through the website) the unpacked folder; /kaggle/input is
# read-only, so either way the inputs are placed under ROOT and then checked against the sha256 manifest.
ARCHIVE = next(Path('/kaggle/input').rglob('harness_inputs.tar.gz'), None)
if ARCHIVE is not None:
    with tarfile.open(ARCHIVE) as archive:
        archive.extractall(ROOT, filter='data')
else:
    import shutil
    FOLDER = next(p.parent for p in Path('/kaggle/input').rglob('harness_inputs/manifest.json'))
    shutil.copytree(FOLDER, INPUTS, dirs_exist_ok=True)
print('inputs from', ARCHIVE or FOLDER, flush=True)
for name, expected in json.loads((INPUTS / 'manifest.json').read_text()).items():
    assert hashlib.sha256((INPUTS / name).read_bytes()).hexdigest() == expected, name

# kaggle-benchmarks 0.6.2 needs protobuf<6 (google-adk alone would pull 6.x) and breaks with hishel 2.x; hold both.
CONSTRAINTS = ROOT / 'constraints.txt'
CONSTRAINTS.write_text('protobuf==5.29.6\nhishel<2\n')

def install(args):
    result = subprocess.run(['uv','pip','install','--python',sys.executable,'-c',str(CONSTRAINTS)] + args,
                            capture_output=True,text=True,timeout=300)
    print(result.stdout[-2000:],result.stderr[-4000:],flush=True)
    if result.returncode:
        raise RuntimeError('Harness dependency installation failed')

install(['google-adk==1.36.1','google-genai==2.11.0','docker==7.1.0','litellm==1.104.2',
         'networkx','numpy','pandas','cachetools','python-dotenv','pyyaml',
         'pytest==9.1.1','pytest-timeout==2.1.0','markdown-it-py==4.2.0','rich==15.0.0'])
# The harness wheels go in with --no-deps: their heavy extras (transformers, torchvision, accelerate) are not used on this
# path; every module they import at run time is in the list above (checked in a local copy of the hosted environment).
install(['--no-deps'] + [str(p) for p in sorted((INPUTS/'harness_wheels').glob('*.whl'))])

# %%
# ADAPTER_SOURCE

# %%
# CONTROLS_SOURCE

# %%
import concurrent.futures
import contextvars
import shutil
import traceback
import yaml
import kaggle_benchmarks as kbench
from adk_submission import GenerationConstraints, NumericRange


async def integration(llm, report):
    controls = await run_controls(INPUTS, ROOT/'hosted_controls', 'subprocess')
    report['controls'] = controls
    cases = controls['cases']
    report['calibration_passed'] = (not cases['empty']['resolved']
                                    and cases['empty']['test_exit_code'] == 1
                                    and cases['reference']['resolved'])
    if not report['calibration_passed']:
        raise RuntimeError('Official grader calibration failed; live model run skipped.')

    bundle = ROOT/'agent_bundle'
    shutil.copytree(INPUTS/'bundle', bundle)
    # Preserve the official tool list and prompt. Change only the model binding
    # and explicitly use a small proxy-compatible generation config for this smoke test.
    source = (bundle/'agent.yaml').read_text().replace(
        'model: gemma-4-e4b-it-qat-w4a16-ct', 'model: kaggle_hosted_model')
    (bundle/'agent.yaml').write_text(source)
    (bundle/'configs/sampling.yaml').write_text('temperature: 0.0\nmax_output_tokens: 2048\n')
    report['sampling'] = {'temperature': 0.0 if getattr(llm, 'support_temperature', True) else 'provider default (proxy does not accept it)',
                          'max_output_tokens': 2048, 'thinking': 'provider default; not the E4B thinking configuration'}
    task = json.loads((INPUTS/'tasks.jsonl').read_text())
    task['problem_statement'] += ('\n\nFor this integration check, apply this supplied reference fix, '
        'verify your changes, then call submit_patch:\n```diff\n' + task['patch'] + '\n```\n')
    tasks = ROOT/'answer_given_tasks.jsonl'
    tasks.write_text(json.dumps(task)+'\n')
    model, client = make_model(llm, ROOT/'model_calls.jsonl')
    registry = ModelRegistry()
    registry.register('kaggle_hosted_model', model)
    config = configuration(INPUTS, ROOT/'agent_run', 'subprocess', registry, tasks, bundle)
    # Empty defaults prevent the compiler from silently adding E4B's thinking budget.
    config.generation_constraints = GenerationConstraints(
        allowed_fields=None, max_output_tokens=NumericRange(1,32768), defaults={})
    await Evaluator(config).run()
    report['agent_result'] = json.loads((ROOT/'agent_run/task_results.jsonl').read_text().splitlines()[0])
    # Count calls from the bridge's own record: the harness copies the registered model, so client.calls stays 0.
    calls_file = ROOT/'model_calls.jsonl'
    report['model_calls'] = len(calls_file.read_text().splitlines()) if calls_file.exists() else 0
    # task_results.jsonl carries only agent_patch_size; the harness writes the patch itself to patches/<task>.patch.
    patch_file = ROOT/'agent_run/patches'/f"{task['instance_id']}.patch"
    patch = patch_file.read_text() if patch_file.exists() else ''
    report['patch_bytes'] = len(patch.encode())
    if report['patch_bytes'] != report['agent_result'].get('agent_patch_size'):
        raise RuntimeError(f"Saved patch is {report['patch_bytes']} bytes; harness reported {report['agent_result'].get('agent_patch_size')}")
    (ROOT/'model.patch').write_text(patch)
    replay = await run_controls(INPUTS, ROOT/'hosted_replay', 'subprocess', patch)
    report['replay'] = replay['cases']['model_patch']
    report['passed'] = bool(report['agent_result']['resolved'] and report['replay']['resolved'] and report['model_calls'])


@kbench.task(name='answer-ladder-official-harness-probe-20261112')
def official_harness_probe(llm) -> bool:
    report = {'model': llm.model, 'backend': 'subprocess', 'scope': 'one-task official harness integration',
              'versions': {p: importlib.metadata.version(p) for p in
                           ['swegemma','adk-submission','adk-eval-core','google-adk','google-genai','litellm']}}
    try:
        ctx = contextvars.copy_context()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(ctx.run, asyncio.run, integration(llm,report)).result()
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
        report['traceback'] = traceback.format_exc()
    finally:
        (ROOT/'integration_report.json').write_text(json.dumps(report,indent=2,default=str)+'\n')
        concise = {k:v for k,v in report.items() if k not in ['controls','agent_result','replay']}
        print('OFFICIAL_HARNESS_REPORT',json.dumps(concise,indent=2),flush=True)
    return bool(report.get('passed'))


# %%
official_harness_probe.run(kbench.llm)
