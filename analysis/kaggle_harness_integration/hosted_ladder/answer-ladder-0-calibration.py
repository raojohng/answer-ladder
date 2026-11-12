# %%
"""Answer Ladder on Kaggle Benchmarks: grader calibration (empty and reference patches, no model).

The competition's own harness (swegemma 0.2.11, official loop: run_command, read_file, edit_file, write_file, submit_patch;
official grader) runs each task in subprocess mode with the benchmark model behind Kaggle's model proxy. The task statement
carries the rung's added paragraph, byte-identical to the paper's official-loop runs. Score = share of tasks resolved.
Inputs: dataset jaejohn/answer-ladder-inputs (task snapshots, task rows, sandbox setup, task wheels; sha256 manifest) and
the competition's public wheelhouse (metric/gemma-4-developer-agent-wheelhouse) for the harness wheels."""
import base64, hashlib, importlib.metadata, json, lzma, os, shutil, subprocess, sys
from pathlib import Path

RUNG = 'calibration'            # ctrl | loc | diff | edits | apply | calibration
TASK_IDS = ['fastapi_11355', 'fastapi_12942', 'fastapi_13207', 'fastapi_13713', 'fastapi_13920', 'fastapi_14246', 'fastapi_14258', 'fastapi_14266', 'fastapi_14301', 'fastapi_14306', 'fastapi_14349', 'fastapi_14356', 'fastapi_14360', 'fastapi_14361', 'fastapi_14372', 'fastapi_14419', 'fastapi_14430', 'fastapi_14448', 'fastapi_14455', 'fastapi_14458', 'fastapi_14459', 'fastapi_14463', 'fastapi_14479', 'fastapi_14482', 'fastapi_14485', 'fastapi_14487', 'fastapi_14492', 'fastapi_14512', 'fastapi_14786', 'fastapi_14794', 'fastapi_14873', 'fastapi_14986', 'fastapi_15023', 'fastapi_15588', 'fastapi_15589', 'fastapi_5077', 'fastapi_5624', 'fastapi_9425', 'fastapi_9555', 'fastapi_9753', 'rich_2725', 'rich_2943', 'rich_3006', 'rich_3043', 'rich_3052', 'rich_3061', 'rich_3063', 'rich_3067', 'rich_3105', 'rich_3180', 'rich_3278', 'rich_3454', 'rich_3470', 'rich_3471', 'rich_3480', 'rich_3506', 'rich_3518', 'rich_3521', 'rich_3535', 'rich_3675', 'rich_3676', 'rich_3718', 'rich_3772', 'rich_3777', 'rich_3882', 'rich_3894', 'rich_3905', 'rich_3934', 'rich_3935', 'rich_3938', 'rich_3942', 'rich_3944', 'rich_3953', 'rich_4006', 'rich_4075', 'rich_4076', 'rich_4077']     # fixed list, chosen before any hosted run
CONCURRENCY = 4
BUDGET = dict(timeout_seconds=60, max_tool_calls=50, max_time_minutes=8, max_turns=100)   # the competition's budget
STATEMENTS_XZ = ''
APPLY_WHEEL = ''

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
(BUNDLE / 'prompts/system.md').write_text(base64.b64decode('WW91IGFyZSBhIGhlbHBmdWwgYXNzaXN0YW50IHRoYXQgY2FuIGludGVyYWN0IHdpdGggYSBjb21wdXRlciBzaGVsbCBhbmQgdGhlIHJlcG9zaXRvcnkncyBmaWxlcyB0byBzb2x2ZSBwcm9ncmFtbWluZyB0YXNrcy4KCjxwcl9kZXNjcmlwdGlvbj4KQ29uc2lkZXIgdGhlIGZvbGxvd2luZyBQUiBkZXNjcmlwdGlvbjoKe3Byb2JsZW1fZGVzY3JpcHRpb259CjwvcHJfZGVzY3JpcHRpb24+Cgo8aW5zdHJ1Y3Rpb25zPgojIFRhc2sgSW5zdHJ1Y3Rpb25zCgojIyBPdmVydmlldwoKWW91J3JlIGEgc29mdHdhcmUgZW5naW5lZXIgaW50ZXJhY3RpbmcgY29udGludW91c2x5IHdpdGggYSBjb21wdXRlciBieSBjYWxsaW5nIHRvb2xzLgpZb3UnbGwgYmUgaGVscGluZyBpbXBsZW1lbnQgbmVjZXNzYXJ5IGNoYW5nZXMgdG8gbWVldCByZXF1aXJlbWVudHMgaW4gdGhlIFBSIGRlc2NyaXB0aW9uLgpZb3VyIHRhc2sgaXMgc3BlY2lmaWNhbGx5IHRvIG1ha2UgY2hhbmdlcyB0byBub24tdGVzdCBmaWxlcyBpbiB0aGUgY3VycmVudCBkaXJlY3RvcnkgaW4gb3JkZXIgdG8gZml4IHRoZSBpc3N1ZSBkZXNjcmliZWQgaW4gdGhlIFBSIGRlc2NyaXB0aW9uIGluIGEgd2F5IHRoYXQgaXMgZ2VuZXJhbCBhbmQgY29uc2lzdGVudCB3aXRoIHRoZSBjb2RlYmFzZS4KPElNUE9SVEFOVD5UaGlzIGlzIGFuIGludGVyYWN0aXZlIHByb2Nlc3Mgd2hlcmUgeW91IHdpbGwgdGhpbmsgYW5kIGlzc3VlIEFUIExFQVNUIE9ORSB0b29sIGNhbGwsIHNlZSB0aGUgcmVzdWx0LCB0aGVuIHRoaW5rIGFuZCBpc3N1ZSB5b3VyIG5leHQgdG9vbCBjYWxsKHMpLjwvaW1wb3J0YW50PgoKRm9yIGVhY2ggcmVzcG9uc2U6CgoxLiBJbmNsdWRlIGEgVEhPVUdIVCBzZWN0aW9uIGV4cGxhaW5pbmcgeW91ciByZWFzb25pbmcgYW5kIHdoYXQgeW91J3JlIHRyeWluZyB0byBhY2NvbXBsaXNoCjIuIFByb3ZpZGUgb25lIG9yIG1vcmUgdG9vbCBjYWxscyB0byBleGVjdXRlCgojIyBUb29scwoKLSBgcnVuX2NvbW1hbmRgOiBydW4gYSBzaGVsbCBjb21tYW5kIChzZWFyY2gsIGxpc3QsIHJ1biBzY3JpcHRzIGFuZCB0ZXN0cykKLSBgcmVhZF9maWxlYDogcmVhZCBhIGZpbGUsIG9yIGEgcmFuZ2Ugb2YgbGluZXMgd2l0aCBzdGFydF9saW5lIGFuZCBlbmRfbGluZQotIGBlZGl0X2ZpbGVgOiBjaGFuZ2UgYW4gZXhpc3RpbmcgZmlsZSBieSByZXBsYWNpbmcgb2xkX3N0cmluZyB3aXRoIG5ld19zdHJpbmc7IGNvcHkgb2xkX3N0cmluZyBleGFjdGx5IGZyb20gd2hhdCByZWFkX2ZpbGUgc2hvd2VkCi0gYHdyaXRlX2ZpbGVgOiBjcmVhdGUgYSBuZXcgZmlsZQotIGBzdWJtaXRfcGF0Y2hgOiBzdWJtaXQgeW91ciBjaGFuZ2VzIHdoZW4geW91IGFyZSBkb25lCgojIyBJbXBvcnRhbnQgQm91bmRhcmllcwoKLSBNT0RJRlk6IFJlZ3VsYXIgc291cmNlIGNvZGUgZmlsZXMgaW4gL3dvcmtzcGFjZSAodGhpcyBpcyB0aGUgd29ya2luZyBkaXJlY3RvcnkgZm9yIGFsbCB5b3VyIHN1YnNlcXVlbnQgY29tbWFuZHMpCi0gRE8gTk9UIE1PRElGWTogVGVzdHMsIGNvbmZpZ3VyYXRpb24gZmlsZXMgKHB5cHJvamVjdC50b21sLCBzZXR1cC5jZmcsIGV0Yy4pCgojIyBSZWNvbW1lbmRlZCBXb3JrZmxvdwoKMS4gQW5hbHl6ZSB0aGUgY29kZWJhc2UgYnkgZmluZGluZyBhbmQgcmVhZGluZyByZWxldmFudCBmaWxlcwoyLiBDcmVhdGUgYSBzY3JpcHQgdG8gcmVwcm9kdWNlIHRoZSBpc3N1ZQozLiBFZGl0IHRoZSBzb3VyY2UgY29kZSB0byByZXNvbHZlIHRoZSBpc3N1ZQo0LiBWZXJpZnkgeW91ciBmaXggd29ya3MgYnkgcnVubmluZyB5b3VyIHNjcmlwdCBhZ2Fpbgo1LiBUZXN0IGVkZ2UgY2FzZXMgdG8gZW5zdXJlIHlvdXIgZml4IGlzIHJvYnVzdAoKIyMgQ29tbWFuZCBFeGVjdXRpb24gUnVsZXMKCllvdSBhcmUgb3BlcmF0aW5nIGluIGFuIGVudmlyb25tZW50IHdoZXJlCgoxLiBZb3UgaXNzdWUgYXQgbGVhc3Qgb25lIHRvb2wgY2FsbAoyLiBUaGUgc3lzdGVtIGV4ZWN1dGVzIGl0CjMuIFlvdSBzZWUgdGhlIHJlc3VsdChzKQo0LiBZb3Ugd3JpdGUgeW91ciBuZXh0IHRvb2wgY2FsbChzKQoKRWFjaCByZXNwb25zZSBzaG91bGQgaW5jbHVkZToKCjEuICoqUmVhc29uaW5nIHRleHQqKiB3aGVyZSB5b3UgZXhwbGFpbiB5b3VyIGFuYWx5c2lzIGFuZCBwbGFuCjIuIEF0IGxlYXN0IG9uZSB0b29sIGNhbGwKCioqQ1JJVElDQUwgUkVRVUlSRU1FTlRTOioqCgotIFlvdXIgcmVzcG9uc2UgU0hPVUxEIGluY2x1ZGUgcmVhc29uaW5nIHRleHQgZXhwbGFpbmluZyB3aGF0IHlvdSdyZSBkb2luZwotIFlvdXIgcmVzcG9uc2UgTVVTVCBpbmNsdWRlIEFUIExFQVNUIE9ORSB0b29sIGNhbGwuIFlvdSBjYW4gbWFrZSBNVUxUSVBMRSB0b29sIGNhbGxzIGluIGEgc2luZ2xlIHJlc3BvbnNlIHdoZW4gdGhleSBhcmUgaW5kZXBlbmRlbnQgKGUuZy4sIHNlYXJjaGluZyBtdWx0aXBsZSBmaWxlcywgcmVhZGluZyBkaWZmZXJlbnQgcGFydHMgb2YgdGhlIGNvZGViYXNlKS4KLSBEaXJlY3Rvcnkgb3IgZW52aXJvbm1lbnQgdmFyaWFibGUgY2hhbmdlcyBhcmUgbm90IHBlcnNpc3RlbnQuIEV2ZXJ5IHJ1bl9jb21tYW5kIGlzIGV4ZWN1dGVkIGluIGEgbmV3IHN1YnNoZWxsLgotIEhvd2V2ZXIsIHlvdSBjYW4gcHJlZml4IGFueSBjb21tYW5kIHdpdGggYE1ZX0VOVl9WQVI9TVlfVkFMVUUgY2QgL3BhdGgvdG8vd29ya2luZy9kaXIgJiYgLi4uYCBvciB3cml0ZS9sb2FkIGVudmlyb25tZW50IHZhcmlhYmxlcyBmcm9tIGZpbGVzCgojIyBFbnZpcm9ubWVudCBEZXRhaWxzCgotIFlvdSBoYXZlIGEgZnVsbCBMaW51eCBzaGVsbCBlbnZpcm9ubWVudAotIEFsd2F5cyB1c2Ugbm9uLWludGVyYWN0aXZlIGZsYWdzICgteSwgLWYpIGZvciBjb21tYW5kcwotIEF2b2lkIGludGVyYWN0aXZlIHRvb2xzIGxpa2UgdmksIG5hbm8sIG9yIGFueSB0aGF0IHJlcXVpcmUgdXNlciBpbnB1dAotIFlvdSBjYW4gdXNlIGJhc2ggY29tbWFuZHMgb3IgaW52b2tlIGFueSB0b29sIHRoYXQgaXMgYXZhaWxhYmxlIGluIHRoZSBlbnZpcm9ubWVudAotIFlvdSBjYW4gYWxzbyBjcmVhdGUgbmV3IHRvb2xzIG9yIHNjcmlwdHMgdG8gaGVscCB5b3Ugd2l0aCB0aGUgdGFzawoKIyMgU3VibWlzc2lvbgoKV2hlbiB5b3UndmUgY29tcGxldGVkIHlvdXIgd29yaywgeW91IE1VU1Qgc3VibWl0IHlvdXIgY2hhbmdlcyB3aXRoIHRoZSBzdWJtaXRfcGF0Y2ggdG9vbC4KRm9sbG93IHRoZXNlIHN0ZXBzIElOIE9SREVSLCB3aXRoIFNFUEFSQVRFIHRvb2wgY2FsbHM6CgpTdGVwIDE6IFJlbW92ZSBldmVyeSBmaWxlIHlvdSBjcmVhdGVkIHRoYXQgaXMgbm90IHBhcnQgb2YgdGhlIGZpeDogcmVwcm9kdWN0aW9uIHNjcmlwdHMsIGhlbHBlciBzY3JpcHRzLCB0ZXN0cyBvciB0b29scyB5b3UgY3JlYXRlZC4gc3VibWl0X3BhdGNoIGluY2x1ZGVzIGV2ZXJ5IGNoYW5nZWQgYW5kIG5ldyBmaWxlIGluIC93b3Jrc3BhY2UuCgo8SU1QT1JUQU5UPgpUaGUgcGF0Y2ggbXVzdCBvbmx5IGNvbnRhaW4gY2hhbmdlcyB0byB0aGUgc3BlY2lmaWMgc291cmNlIGZpbGVzIHlvdSBtb2RpZmllZCB0byBmaXggdGhlIGlzc3VlLgpEbyBub3Qgc3VibWl0IGZpbGUgY3JlYXRpb25zIG9yIGNoYW5nZXMgdG8gYW55IG9mIHRoZSBmb2xsb3dpbmcgZmlsZXM6CgotIHRlc3QgYW5kIHJlcHJvZHVjdGlvbiBmaWxlcwotIGhlbHBlciBzY3JpcHRzLCB0ZXN0cywgb3IgdG9vbHMgdGhhdCB5b3UgY3JlYXRlZAotIGluc3RhbGxhdGlvbiwgYnVpbGQsIHBhY2thZ2luZywgY29uZmlndXJhdGlvbiwgb3Igc2V0dXAgc2NyaXB0cyB1bmxlc3MgdGhleSBhcmUgZGlyZWN0bHkgcGFydCBvZiB0aGUgaXNzdWUgeW91IHdlcmUgZml4aW5nICh5b3UgY2FuIGFzc3VtZSB0aGF0IHRoZSBlbnZpcm9ubWVudCBpcyBhbHJlYWR5IHNldCB1cCBmb3IgeW91ciBjbGllbnQpCi0gYmluYXJ5IG9yIGNvbXBpbGVkIGZpbGVzCjwvSU1QT1JUQU5UPgoKU3RlcCAyOiBWZXJpZnkgeW91ciBwYXRjaApSdW4gYGdpdCBzdGF0dXMgJiYgZ2l0IGRpZmZgIHRvIGNvbmZpcm0gdGhlIHdvcmtpbmcgdHJlZSBvbmx5IGNvbnRhaW5zIHlvdXIgaW50ZW5kZWQgY2hhbmdlcy4KClN0ZXAgMzogU3VibWl0CkNhbGwgdGhlIHN1Ym1pdF9wYXRjaCB0b29sLgoKPENSSVRJQ0FMPgotIFZlcmlmeWluZyB0aGUgcGF0Y2ggYW5kIHN1Ym1pdHRpbmcgaXQgTVVTVCBiZSBzZXBhcmF0ZSBzdGVwcy4KLSBJZiB5b3UgY2hhbmdlIGFueSBmaWxlIGFmdGVyIHZlcmlmeWluZywgeW91IFNIT1VMRCB2ZXJpZnkgYWdhaW4gYmVmb3JlIHN1Ym1pdHRpbmcuCi0gWW91IENBTk5PVCBjb250aW51ZSB3b3JraW5nIChyZWFkaW5nLCBlZGl0aW5nLCB0ZXN0aW5nKSBpbiBhbnkgd2F5IG9uIHRoaXMgdGFzayBhZnRlciBzdWJtaXR0aW5nLgo8L0NSSVRJQ0FMPgo8L2luc3RydWN0aW9ucz4K').decode())
(BUNDLE / 'agent.yaml').write_text('name: swe_agent\nmodel: kaggle_hosted_model\ninstruction: !include prompts/system.md\n'
                                   'tools:\n  - run_command\n  - read_file\n  - edit_file\n  - write_file\n  - submit_patch\n'
                                   'generate_content_config: !include configs/sampling.yaml\n')
# Provider defaults: the proxy accepts no temperature/top_k, and thinking is the provider's own (not E4B's budget).
(BUNDLE / 'configs/sampling.yaml').write_text('max_output_tokens: 8192\n')
(BUNDLE / 'eval_config.yaml').write_text('evaluation:\n' + ''.join(f'  {k}: {v}\n' for k, v in BUDGET.items()))
os.environ['KAGGLE_SANDBOX_DIR'] = str(ROOT / 'sandbox')

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


@kbench.task(name='answer-ladder-0-calibration')
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
