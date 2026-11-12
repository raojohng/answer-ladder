"""Stage immutable official inputs for a private harness integration test."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PAYLOAD = HERE / 'payload'
PAYLOAD.mkdir(exist_ok=True)
task = next(json.loads(line) for line in (ROOT / 'data/tasks.jsonl').read_text().splitlines()
            if json.loads(line)['instance_id'] == 'rich_3278')
for name in ['snapshots', 'harness_wheels', 'wheels', 'sandbox', 'bundle/prompts', 'bundle/configs']:
    (PAYLOAD / name).mkdir(parents=True, exist_ok=True)
(PAYLOAD / 'tasks.jsonl').write_text(json.dumps(task) + '\n')
shutil.copy2(ROOT / 'data/snapshots/rich_3278.tgz', PAYLOAD / 'snapshots/rich_3278.tgz')
shutil.copy2(ROOT / 'data/sandbox/setup.py', PAYLOAD / 'sandbox/setup.py')
for name in ['swegemma-0.2.11-py3-none-any.whl', 'adk_submission-0.2.13-py3-none-any.whl',
             'adk_eval_core-0.1.0-py3-none-any.whl']:
    shutil.copy2(ROOT / 'wheelhouse' / name, PAYLOAD / 'harness_wheels' / name)
# Exact public task dependency wheelhouse, not the model-serving wheelhouse.
for source in (ROOT / 'data/wheels').glob('*.whl'):
    shutil.copy2(source, PAYLOAD / 'wheels' / source.name)
bundle = ROOT / 'paper_track/release/answer_ladder/bundles/e4b_off_ctrl_v1'
for name in ['agent.yaml', 'prompts/system.md', 'configs/sampling.yaml', 'eval_config.yaml']:
    shutil.copy2(bundle / name, PAYLOAD / 'bundle' / name)
manifest = {str(p.relative_to(PAYLOAD)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(PAYLOAD.rglob('*')) if p.is_file() and p.name != 'manifest.json'}
(PAYLOAD / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
upload = HERE / 'private_dataset'
upload.mkdir(exist_ok=True)
with tarfile.open(upload / 'harness_inputs.tar.gz', 'w:gz', compresslevel=1) as archive:
    archive.add(PAYLOAD, arcname='harness_inputs')
(upload / 'dataset-metadata.json').write_text(json.dumps({
    'id': 'jaejohn/answer-ladder-harness-probe-inputs',
    'title': 'Answer Ladder private harness probe inputs',
    'licenses': [{'name': 'apache-2.0'}],
}, indent=2) + '\n')
print('Staged',len(manifest),'hashed input files; private upload bytes:',(upload/'harness_inputs.tar.gz').stat().st_size)
