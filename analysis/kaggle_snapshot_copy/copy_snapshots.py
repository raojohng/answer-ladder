"""Copy the Answer Ladder's 77 task snapshots (plus their task rows, the sandbox setup and the task wheels) from the mounted
competition data into /kaggle/working, with a sha256 manifest, so the output can become a private dataset that Kaggle
Benchmarks tasks can attach (they accept datasets, not competitions). Data never leaves Kaggle."""
import hashlib, json, shutil
from pathlib import Path

IDS = ["fastapi_11355", "fastapi_12942", "fastapi_13207", "fastapi_13713", "fastapi_13920", "fastapi_14246", "fastapi_14258", "fastapi_14266", "fastapi_14301", "fastapi_14306", "fastapi_14349", "fastapi_14356", "fastapi_14360", "fastapi_14361", "fastapi_14372", "fastapi_14419", "fastapi_14430", "fastapi_14448", "fastapi_14455", "fastapi_14458", "fastapi_14459", "fastapi_14463", "fastapi_14479", "fastapi_14482", "fastapi_14485", "fastapi_14487", "fastapi_14492", "fastapi_14512", "fastapi_14786", "fastapi_14794", "fastapi_14873", "fastapi_14986", "fastapi_15023", "fastapi_15588", "fastapi_15589", "fastapi_5077", "fastapi_5624", "fastapi_9425", "fastapi_9555", "fastapi_9753", "rich_2725", "rich_2943", "rich_3006", "rich_3043", "rich_3052", "rich_3061", "rich_3063", "rich_3067", "rich_3105", "rich_3180", "rich_3278", "rich_3454", "rich_3470", "rich_3471", "rich_3480", "rich_3506", "rich_3518", "rich_3521", "rich_3535", "rich_3675", "rich_3676", "rich_3718", "rich_3772", "rich_3777", "rich_3882", "rich_3894", "rich_3905", "rich_3934", "rich_3935", "rich_3938", "rich_3942", "rich_3944", "rich_3953", "rich_4006", "rich_4075", "rich_4076", "rich_4077"]
# glob (not rglob) so symlinked mounts are followed; the competition sits 1-3 levels below /kaggle/input.
SRC = next(p.parent for pat in ('*/tasks.jsonl', '*/*/tasks.jsonl', '*/*/*/tasks.jsonl')
           for p in sorted(Path('/kaggle/input').glob(pat)) if (p.parent / 'snapshots').is_dir())
OUT = Path('/kaggle/working/answer_ladder_inputs')
print('competition data at', SRC, flush=True)
(OUT / 'snapshots').mkdir(parents=True, exist_ok=True)
rows = {json.loads(l)['instance_id']: l for l in (SRC / 'tasks.jsonl').read_text().splitlines() if l.strip()}
missing = [i for i in IDS if i not in rows or not (SRC / 'snapshots' / f'{i}.tgz').exists()]
assert not missing, f'missing in competition data: {missing}'
(OUT / 'tasks.jsonl').write_text(''.join(rows[i] + '\n' for i in IDS))
(OUT / 'ids_77.txt').write_text(''.join(i + '\n' for i in IDS))
for n, i in enumerate(IDS, 1):
    shutil.copyfile(SRC / 'snapshots' / f'{i}.tgz', OUT / 'snapshots' / f'{i}.tgz')
    if n % 10 == 0:
        print('copied', n, 'of', len(IDS), flush=True)
# contents only (copyfile): the mounted inputs are read-only and their permissions must not reach the output.
for sub, pattern in (('sandbox', '*.py'), ('wheels', '*.whl')):
    (OUT / sub).mkdir(exist_ok=True)
    for f in sorted((SRC / sub).glob(pattern)):
        shutil.copyfile(f, OUT / sub / f.name)


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


manifest = {str(p.relative_to(OUT)): sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()}
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n')
size = sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())
print(f'COPY_DONE {len(IDS)} tasks, {len(manifest)} files, {size / 1e9:.2f} GB', flush=True)
