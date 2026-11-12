"""Stage the public GitHub repository for the paper: a curated, scrubbed copy laid out like paper_track/ (so every path in
REPRODUCE.md works), plus the e4b_track/rtx run scripts REPRODUCE.md names. Sessions and task snapshots stay on Kaggle.
    python3 -I paper_track/analysis/stage_github.py <paper version, e.g. paper_v14.md> <stage dir>      (from the repo root)
Then scans the stage for personal strings, addresses and secrets; prints what it found (must be none)."""
import re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # Gemma4Take2/
PT = ROOT / "paper_track"
version, stage = sys.argv[1], Path(sys.argv[2]).resolve()
if stage.exists():
    shutil.rmtree(stage)
stage.mkdir(parents=True)

SKIP_DIRS = {"__pycache__", "payload", "private_dataset", "sessions", "hosted_v1", "hosted_v2", "hosted_repository_v1",
             "hosted_repository_v2", "hosted_v1_probe", "local_docker_v1", "local_subprocess_v1", "local_docker_replay_v2",
             "test_outputs", "logs", "traces", "patches"}
SKIP_FILES = re.compile(r"(\.pyc|\.tar|\.tgz|\.tar\.gz|\.whl\.part)$")
TEXT = re.compile(r"\.(py|md|txt|json|jsonl|csv|sh|yaml|yml|ipynb|log)$")
SCRUB = [(re.compile(r"?"), ""), (re.compile(r"/home/(user|user)"), "~"),
         (re.compile(r"user@100\.64\.18\.0"), "user@gpu-host"), (re.compile(r"100\.64\.18\.0"), "gpu-host"),
         (re.compile(r"\b(user|user)\b"), "user"), (re.compile("anub" + "huti", re.I), "user"), (re.compile(r"<local data>"']*"), "<local data>")]


def copy(src, dst):
    if src.is_dir():
        for p in sorted(src.rglob("*")):
            rel = p.relative_to(src)
            if any(part in SKIP_DIRS for part in rel.parts) or p.is_dir() or SKIP_FILES.search(p.name):
                continue
            copy(p, dst / rel)
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if TEXT.search(src.name):
        text = src.read_text(errors="replace")
        for pat, rep in SCRUB:
            text = pat.sub(rep, text)
        dst.write_text(text)
    else:
        shutil.copyfile(src, dst)


copy(PT / version, stage / "paper.md")
copy(PT / "release/github_README.md", stage / "README.md")
if (PT / "release/paper.pdf").exists():
    shutil.copyfile(PT / "release/paper.pdf", stage / "paper.pdf")
(stage / "LICENSE").write_text(__import__("urllib.request").request.urlopen("https://www.apache.org/licenses/LICENSE-2.0.txt", timeout=60).read().decode())
for d in ("figures", "data", "annotation", "tables", "analysis"):
    copy(PT / d, stage / d)
copy(PT / "REPRODUCE.md", stage / "REPRODUCE.md")
copy(PT / "release/answer_ladder", stage / "release/answer_ladder")     # minus sessions/ (on Kaggle)
copy(PT / "release/notebook", stage / "release/notebook")
for f in ("ladder2_test.sh", "ladder3_prep.py", "ladder3_test.sh", "ladder4_prep.py", "ladder4_test.sh", "ladder56_prep.py",
          "ladder5_test.sh", "ladder6_test.sh", "ladder8_prep.py", "ladder8_test.sh", "run_tasks.py", "trajectory_stages.py",
          "release_pack.py", "assemble_release.sh", "score.py", "common.py"):
    if (ROOT / "e4b_track/rtx" / f).exists():
        copy(ROOT / "e4b_track/rtx" / f, stage / "e4b_track/rtx" / f)

# scan
bad = []
SECRET = re.compile(r"(KGAT_[A-Za-z0-9]+|\"key\"\s*:\s*\"[0-9a-f]{32}\"|MODEL_PROXY_API_KEY\s*=\s*\S+|ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,})")
PERSONAL = re.compile(r"(user|user|" + "anub" + "huti" + r"|100\.64\.\d+\.\d+|/home/(?!user\b)[a-z]|<local data>", re.I)
for p in stage.rglob("*"):
    if p.is_file() and TEXT.search(p.name):
        t = p.read_text(errors="replace")
        for m in list(SECRET.finditer(t))[:1] + list(PERSONAL.finditer(t))[:1]:
            bad.append((str(p.relative_to(stage)), m.group(0)[:40]))
size = sum(p.stat().st_size for p in stage.rglob("*") if p.is_file())
big = sorted(((p.stat().st_size, str(p.relative_to(stage))) for p in stage.rglob("*") if p.is_file()), reverse=True)[:5]
print(f"staged {sum(1 for p in stage.rglob('*') if p.is_file())} files, {size / 1e6:.1f} MB; largest: {[(round(s / 1e6, 1), n) for s, n in big]}")
print("FINDINGS:", bad if bad else "none")
