# %%
"""Answer Ladder on Kaggle Benchmarks: rung 1, no help ("find this in the repository yourself").

The competition's own harness (swegemma 0.2.11, official loop: run_command, read_file, edit_file, write_file, submit_patch;
official grader) runs each task in subprocess mode with the benchmark model behind Kaggle's model proxy. The task statement
carries the rung's added paragraph, byte-identical to the paper's official-loop runs. Score = share of tasks resolved.
Inputs: dataset jaejohn/answer-ladder-inputs (task snapshots, task rows, sandbox setup, task wheels; sha256 manifest) and
the competition's public wheelhouse (metric/gemma-4-developer-agent-wheelhouse) for the harness wheels."""
import base64, hashlib, importlib.metadata, json, lzma, os, shutil, subprocess, sys
from pathlib import Path

RUNG = 'ctrl'            # ctrl | loc | diff | edits | apply | calibration
TASK_IDS = ['fastapi_11355', 'fastapi_12942', 'fastapi_13207', 'fastapi_13713', 'fastapi_13920', 'fastapi_14246', 'fastapi_14258', 'fastapi_14266', 'fastapi_14301', 'fastapi_14306', 'fastapi_14349', 'fastapi_14356', 'fastapi_14360', 'fastapi_14361', 'fastapi_14372', 'fastapi_14419', 'fastapi_14430', 'fastapi_14448', 'fastapi_14455', 'fastapi_14458', 'fastapi_14459', 'fastapi_14463', 'fastapi_14479', 'fastapi_14482', 'fastapi_14485', 'fastapi_14487', 'fastapi_14492', 'fastapi_14512', 'fastapi_14786', 'fastapi_14794', 'fastapi_14873', 'fastapi_14986', 'fastapi_15023', 'fastapi_15588', 'fastapi_15589', 'fastapi_5077', 'fastapi_5624', 'fastapi_9425', 'fastapi_9555', 'fastapi_9753', 'rich_2725', 'rich_2943', 'rich_3006', 'rich_3043', 'rich_3052', 'rich_3061', 'rich_3063', 'rich_3067', 'rich_3105', 'rich_3180', 'rich_3278', 'rich_3454', 'rich_3470', 'rich_3471', 'rich_3480', 'rich_3506', 'rich_3518', 'rich_3521', 'rich_3535', 'rich_3675', 'rich_3676', 'rich_3718', 'rich_3772', 'rich_3777', 'rich_3882', 'rich_3894', 'rich_3905', 'rich_3934', 'rich_3935', 'rich_3938', 'rich_3942', 'rich_3944', 'rich_3953', 'rich_4006', 'rich_4075', 'rich_4076', 'rich_4077']     # fixed list, chosen before any hosted run
CONCURRENCY = 4
BUDGET = dict(timeout_seconds=60, max_tool_calls=50, max_time_minutes=8, max_turns=100)   # the competition's budget
STATEMENTS_XZ = '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'
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


@kbench.task(name='answer-ladder-1-no-help')
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
