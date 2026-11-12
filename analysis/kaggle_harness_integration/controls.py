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


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--backend', choices=['docker','subprocess'], required=True)
    parser.add_argument('--patch', type=Path)
    args = parser.parse_args()
    asyncio.run(run_controls(args.inputs.resolve(), args.output.resolve(), args.backend,
                             args.patch.read_text() if args.patch else None))
