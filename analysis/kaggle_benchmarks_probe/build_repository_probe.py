"""Embed the one selected real task into the standalone private probe."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
rows = [json.loads(line) for line in (ROOT / 'data/tasks.jsonl').read_text().splitlines() if line.strip()]
task = next(row for row in rows if row['instance_id'] == 'rich_3278')
payload = {key: task[key] for key in ('instance_id', 'repo', 'base_commit', 'patch', 'test_patch')}
# The competition JSON strings omit terminal newlines; git apply needs one.
for key in ('patch', 'test_patch'):
    payload[key] = payload[key].rstrip('\n') + '\n'
template = (HERE / 'repository_probe_template.py').read_text()
source = template.replace('TASK = None  # Replaced by build_repository_probe.py.', 'TASK = ' + repr(payload))
compile(source, 'repository_probe.py', 'exec')
(HERE / 'repository_probe.py').write_text(source)
print('Built repository_probe.py for', payload['instance_id'], 'at', payload['base_commit'])
