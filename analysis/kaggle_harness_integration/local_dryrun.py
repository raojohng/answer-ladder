"""Local dry run of hosted_probe.py's integration() with a scripted fake model, before spending a hosted run.

Runs the same code as the hosted task (cells 2-4 of hosted_probe.py: adapter, controls, integration) on the local payload in
subprocess mode. The fake model speaks the OpenAI chat API that Kaggle's proxy client exposes: it applies the supplied patch with
run_command, calls submit_patch, then stops. Checks every request the bridge sent (tool list, tool_call_id round trip, no
temperature when DROP_TEMPERATURE is set) and that the official grader and the fresh replay both resolve the task.
    .venv/bin/python -I paper_track/analysis/kaggle_harness_integration/local_dryrun.py <out dir (must not exist)>"""
import asyncio, base64, json, sys
from pathlib import Path
from types import SimpleNamespace

from openai.types.chat import ChatCompletion

HERE = Path(__file__).resolve().parent
OUT = Path(sys.argv[1]).resolve()
OUT.mkdir(parents=True)
source = (HERE / 'hosted_probe.py').read_text().split('# %%')
# cell 0 is empty, 1 = archive + installs (hosted only), 2 = adapter, 3 = controls, 4 = integration + task, 5 = run.
cell4 = source[4].split('@kbench.task')[0].replace('import kaggle_benchmarks as kbench\n', '')
glb = {'__name__': 'dryrun', 'INPUTS': HERE / 'payload', 'ROOT': OUT}
exec(compile('import asyncio, json\nfrom pathlib import Path\n' + source[2] + source[3] + cell4, 'hosted_probe.py', 'exec'), glb)

task = json.loads((HERE / 'payload/tasks.jsonl').read_text())
patch = task['patch'] if task['patch'].endswith('\n') else task['patch'] + '\n'
apply_cmd = f"echo {base64.b64encode(patch.encode()).decode()} | base64 -d | git apply && git diff --stat"
requests = []


def create(**request):
    requests.append(request)
    n = len(requests)
    if n == 1:
        msg = {'role': 'assistant', 'tool_calls': [{'id': 'call_apply_1', 'type': 'function',
               'function': {'name': 'run_command', 'arguments': json.dumps({'command': apply_cmd})}}]}
    elif n == 2:
        msg = {'role': 'assistant', 'tool_calls': [{'id': 'call_submit_2', 'type': 'function',
               'function': {'name': 'submit_patch', 'arguments': '{}'}}]}
    else:
        msg = {'role': 'assistant', 'content': 'Submitted.'}
    return ChatCompletion.model_validate({'id': f'dry-{n}', 'object': 'chat.completion', 'created': 0, 'model': 'dry-model',
        'choices': [{'index': 0, 'message': msg, 'finish_reason': 'tool_calls' if n < 3 else 'stop'}],
        'usage': {'prompt_tokens': 100, 'completion_tokens': 10, 'total_tokens': 110}})


llm = SimpleNamespace(model='dry-model', support_temperature=False, client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
glb['make_model'] = (lambda real: (lambda l, p, record_sdk=True: real(l, p, record_sdk=False)))(glb['make_model'])
report = {'model': 'dry-model'}
asyncio.run(glb['integration'](llm, report))
(OUT / 'dryrun_report.json').write_text(json.dumps(report, indent=2, default=str) + '\n')

names = [t['function']['name'] for t in requests[0].get('tools', [])]
tool_msgs = [m for r in requests[1:] for m in r['messages'] if m.get('role') == 'tool']
checks = {
    'calibration_passed': report.get('calibration_passed'),
    'official tools offered': sorted(names) == sorted(['run_command', 'read_file', 'edit_file', 'write_file', 'submit_patch']),
    'tool_call_id round trip': {m.get('tool_call_id') for m in tool_msgs} >= {'call_apply_1'},
    'no temperature sent': all('temperature' not in r for r in requests),
    'agent resolved': report.get('agent_result', {}).get('resolved'),
    'replay resolved': report.get('replay', {}).get('resolved'),
    'passed': report.get('passed'),
}
print('model calls', len(requests), '| tools', names)
for k, v in checks.items():
    print(f'  {k}: {v}')
print('DRYRUN_OK' if all(checks.values()) else 'DRYRUN_FAILED')
