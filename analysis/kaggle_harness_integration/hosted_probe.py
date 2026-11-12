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
"""Use ADK's official LiteLlm conversion with Kaggle's supplied model client.

ADK and swegemma own the agent/tool loop. This bridge only transports each
completion request and records its input/output. No tools execute in the SDK.
"""
import asyncio
import json
from pathlib import Path
import time

from google.adk.models.lite_llm import LiteLlm, LiteLLMClient
from litellm import ModelResponse


class KaggleCompletionClient(LiteLLMClient):
    def __init__(self, llm, record_path, record_sdk=True):
        self.llm = llm
        self.record_path = Path(record_path)
        self.record_sdk = record_sdk
        self.calls = 0

    async def acompletion(self, model, messages, tools=None, response_format=None, **kwargs):
        if kwargs.pop('stream', False):
            raise ValueError('The harness bridge currently supports non-streaming runs only.')
        # Preserve standard sampling parameters. Reject unsupported ones visibly.
        allowed = {'temperature', 'top_p', 'max_tokens', 'max_completion_tokens', 'stop',
                   'presence_penalty', 'frequency_penalty', 'seed', 'tool_choice',
                   'parallel_tool_calls', 'reasoning_effort', 'extra_body', 'timeout'}
        unknown = set(kwargs) - allowed
        if unknown:
            raise ValueError(f'Unmapped generation options: {sorted(unknown)}')
        # Kaggle's SDK never sends temperature through its model proxy (support_temperature=False, proxy bug
        # b/439876083 in kaggle_benchmarks/kaggle/model_proxy.py); mirror it and record what was dropped.
        dropped = {}
        if not getattr(self.llm, 'support_temperature', True) and 'temperature' in kwargs:
            dropped['temperature'] = kwargs.pop('temperature')
        request = dict(model=self.llm.model, messages=messages, **kwargs)
        if tools:
            request['tools'] = tools
        if response_format:
            request['response_format'] = response_format
        self.calls += 1
        started = time.monotonic()
        raw = await asyncio.to_thread(self.llm.client.chat.completions.create, **request)
        response = raw.model_dump(mode='json', exclude_none=True)
        row = dict(call=self.calls, request=request, response=response, dropped=dropped,
                   seconds=time.monotonic() - started)
        if self.record_sdk:
            # Recording into Kaggle's chat log is evidence, not part of the agent loop: a failure here must not end the run.
            try:
                import kaggle_benchmarks as kbench
                from kaggle_benchmarks.messages import Message
                from kaggle_benchmarks.actors import user
                usage = response.get('usage') or {}
                cost = usage.get('cost') or {}
                meta = dict(input_tokens=usage.get('prompt_tokens'), output_tokens=usage.get('completion_tokens'),
                            total_backend_latency_ms=usage.get('total_backend_latency_ms'), **cost)
                # Separate recorded conversations prevent duplicated cumulative history
                # from being mistaken for newly generated training turns.
                with kbench.chats.new(name=f'Official harness model call {self.calls}'):
                    user.send(json.dumps(request, default=str))
                    self.llm.send(Message(content=json.dumps(response['choices'][0]['message']),
                                          sender=self.llm, _meta=meta))
            except Exception as exc:
                row['sdk_record_error'] = f'{type(exc).__name__}: {exc}'
        self.record_path.parent.mkdir(parents=True, exist_ok=True)
        with self.record_path.open('a') as out:
            out.write(json.dumps(row, default=str) + '\n')
        return ModelResponse(**response)


def make_model(llm, record_path, record_sdk=True):
    if not hasattr(getattr(llm, 'client', None), 'chat'):
        raise TypeError('This adapter requires Kaggle\'s OpenAI-compatible model client.')
    client = KaggleCompletionClient(llm, record_path, record_sdk=record_sdk)
    model = LiteLlm(model='openai/' + llm.model, llm_client=client)
    return model, client


# %%
"""Official Evaluator grading of identical fixed patches on either backend."""
import asyncio
import json
import os
from pathlib import Path

from adk_eval_core.tracing import SessionTrace
from adk_submission.registry import ModelRegistry
from swegemma.evaluate import EvalConfig, Evaluator


class FixedPatchEvaluator(Evaluator):
    def __init__(self, config, patch):
        super().__init__(config)
        self.fixed_patch = patch

    async def _run_agent_sandbox(self, task, snapshot_path, task_index, total_tasks, **kwargs):
        return self.fixed_patch, None, SessionTrace()


def configuration(inputs, output, backend, models=None, tasks=None, bundle=None):
    return EvalConfig(
        tasks_path=tasks or inputs / 'tasks.jsonl', snapshots_dir=inputs / 'snapshots',
        results_dir=output, submission_dir=bundle or inputs / 'bundle',
        models=models or ModelRegistry(), sandbox=backend,
        wheels_dir=inputs / 'wheels', task_ids=['rich_3278'],
        image='swebench-sandbox:latest', concurrency=1, display_mode='quiet',
        timeout_seconds=60, verification_timeout_seconds=180,
        max_time_minutes=4, max_tool_calls=20, max_turns=30,
    )


async def run_controls(inputs, output, backend, extra_patch=None):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['KAGGLE_SANDBOX_DIR'] = str(inputs / 'sandbox')
    task = json.loads((inputs / 'tasks.jsonl').read_text())
    patches = {'empty': '', 'reference': task['patch']}
    if extra_patch is not None:
        patches['model_patch'] = extra_patch
    report = {'backend': backend, 'task': task['instance_id'], 'cases': {}}
    for name, patch in patches.items():
        evaluator = FixedPatchEvaluator(configuration(inputs, output / name, backend), patch)
        await evaluator.run()
        row = json.loads((output / name / 'task_results.jsonl').read_text().splitlines()[0])
        report['cases'][name] = row
        print(backend, name, 'resolved=',row['resolved'],'exit=',row.get('test_exit_code'),
              'error=',row.get('error'), flush=True)
        (output / 'control_report.json').write_text(json.dumps(report, indent=2, default=str) + '\n')
    return report




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
