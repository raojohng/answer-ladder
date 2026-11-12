# %%
"""Private smoke test of one real task, not a benchmark score or harness parity test.

The builder injects the selected task's reference and test patches below.
Only fixed apply/verify operations are exposed to the hosted model.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

import kaggle_benchmarks as kbench

TASK = None  # Replaced by build_repository_probe.py.


def command(args, cwd=None, stdin=None, timeout=120, env=None):
    start = time.monotonic()
    try:
        p = subprocess.run(args, cwd=cwd, input=stdin, text=True, capture_output=True,
                           timeout=timeout, env=env)
        return dict(returncode=p.returncode, stdout=p.stdout[-6000:], stderr=p.stderr[-4000:],
                    seconds=round(time.monotonic() - start, 3))
    except (OSError, subprocess.TimeoutExpired) as exc:
        return dict(returncode=None, error=str(exc)[:1000])


def require(result):
    if result['returncode'] != 0:
        raise RuntimeError(json.dumps(result))


# %%
@kbench.task(name="answer-ladder-repository-probe-20261112")
def repository_probe(llm) -> bool:
    """Test a fixed reference action and fresh-checkout pytest verification."""
    report = dict(probe_version=1, task_id=TASK['instance_id'], base_commit=TASK['base_commit'],
                  scope='one real task, subprocess integration smoke test', setup={}, tool_events=[])
    try:
        with tempfile.TemporaryDirectory(prefix='answer-ladder-repository-') as tmp:
            root = Path(tmp)
            original = root / 'original'
            original.mkdir()
            setup = report['setup']
            setup['git_init'] = command(['git', 'init', '-q'], cwd=original)
            require(setup['git_init'])
            setup['fetch'] = command(['git', 'fetch', '--depth=1',
                                     'https://github.com/' + TASK['repo'] + '.git', TASK['base_commit']],
                                    cwd=original)
            require(setup['fetch'])
            setup['checkout'] = command(['git', 'checkout', '-q', '--detach', 'FETCH_HEAD'], cwd=original)
            require(setup['checkout'])
            setup['commit'] = command(['git', 'rev-parse', 'HEAD'], cwd=original)
            require(setup['commit'])
            assert setup['commit']['stdout'].strip() == TASK['base_commit']
            venv = root / 'venv'
            setup['venv'] = command(['uv', 'venv', '--python', sys.executable, str(venv)])
            require(setup['venv'])
            python = str(venv / 'bin/python')
            setup['dependencies'] = command(['uv', 'pip', 'install', '--python', python,
                                             'pytest==8.3.5', str(original)])
            require(setup['dependencies'])
            setup['packages'] = command(['uv', 'pip', 'freeze', '--python', python])
            agent = root / 'agent'
            shutil.copytree(original, agent)
            counter = 0

            def verify_patch(patch):
                nonlocal counter
                counter += 1
                checkout = root / f'verify_{counter}'
                shutil.copytree(original, checkout)
                result = {}
                if patch.strip():
                    result['apply_candidate'] = command(['git', 'apply', '-'], cwd=checkout, stdin=patch)
                    require(result['apply_candidate'])
                result['apply_test_patch'] = command(['git', 'apply', '-'], cwd=checkout, stdin=TASK['test_patch'])
                require(result['apply_test_patch'])
                env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
                           PYTHONPATH=str(checkout))
                result['pytest'] = command([python, '-B', '-m', 'pytest', '-q', '-o', 'addopts=',
                                           'tests/test_ansi.py'], cwd=checkout, env=env)
                return result

            report['empty_patch'] = verify_patch('')
            report['reference_patch'] = verify_patch(TASK['patch'])
            report['calibration_passed'] = (
                report['empty_patch']['pytest']['returncode'] == 1
                and report['reference_patch']['pytest']['returncode'] == 0
            )
            if not report['calibration_passed']:
                raise RuntimeError('Real-task calibration failed; model call skipped.')

            def apply_supplied_fix() -> str:
                """Apply the supplied reference fix to the repository."""
                if len(report['tool_events']) >= 6:
                    raise RuntimeError('Probe tool budget exhausted')
                result = command(['git', 'apply', '-'], cwd=agent, stdin=TASK['patch'])
                report['tool_events'].append(dict(tool='apply_supplied_fix', result=result))
                return json.dumps(result)

            def submit_and_verify() -> str:
                """Submit the current patch for testing in a fresh repository copy."""
                if len(report['tool_events']) >= 6:
                    raise RuntimeError('Probe tool budget exhausted')
                diff = command(['git', 'diff', '--binary'], cwd=agent)
                require(diff)
                result = verify_patch(diff['stdout'])
                report['tool_events'].append(dict(tool='submit_and_verify', result=result))
                return json.dumps(result['pytest'])

            try:
                response = llm.prompt(
                    'This is a compatibility smoke test on a real repository bug. '
                    'Call apply_supplied_fix once, then submit_and_verify once. '
                    'Report the result briefly and stop. The reference fix is:\n' + TASK['patch'],
                    tools=[apply_supplied_fix, submit_and_verify],
                )
                report['model_response'] = str(response)[:3000]
            except Exception as exc:
                report['model_error'] = f'{type(exc).__name__}: {exc}'[:2000]
            report['final_diff'] = command(['git', 'diff', '--binary'], cwd=agent)
            require(report['final_diff'])
            report['final_verification'] = verify_patch(report['final_diff']['stdout'])
            report['model_workflow_passed'] = (
                bool(report['final_diff']['stdout'].strip())
                and report['final_verification']['pytest']['returncode'] == 0
                and any(e['tool'] == 'apply_supplied_fix' and e['result']['returncode'] == 0
                        for e in report['tool_events'])
                and any(e['tool'] == 'submit_and_verify' and e['result']['pytest']['returncode'] == 0
                        for e in report['tool_events'])
            )
    except Exception as exc:
        report['probe_error'] = f'{type(exc).__name__}: {exc}'[:2000]
    finally:
        Path('answer_ladder_repository_probe.json').write_text(json.dumps(report, indent=2) + '\n')
        print('ANSWER_LADDER_REPOSITORY_REPORT\n' + json.dumps(report, indent=2))
    return bool(report.get('calibration_passed') and report.get('model_workflow_passed'))


# %%
if __name__ == '__main__':
    repository_probe.run(kbench.llm)
