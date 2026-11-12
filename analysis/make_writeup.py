"""Kaggle Writeup text from a paper version: the paper itself (title, subtitle, abstract, sections, references), with figure
paths pointed at the public GitHub copy so the images render, and the Project Links to paste into the Writeup's links field.
    python3 -I make_writeup.py paper_v<N>.md out.md      (run from paper_track/)"""
import re, sys
from pathlib import Path

REPO = "https://raw.githubusercontent.com/raojohng/answer-ladder/main/"
LINKS = [("Paper (PDF)", "https://github.com/raojohng/answer-ladder/blob/main/paper.pdf"),
         ("Code and data (GitHub)", "https://github.com/raojohng/answer-ladder"),
         ("Benchmark dataset", "https://www.kaggle.com/datasets/jaejohn/answer-ladder"),
         ("Task inputs for hosted runs", "https://www.kaggle.com/datasets/jaejohn/answer-ladder-inputs"),
         ("Reproduce every table (notebook)", "https://www.kaggle.com/code/jaejohn/answer-ladder-reproduce-and-score"),
         ("Run the ladder on Kaggle Benchmarks (notebook)", "https://www.kaggle.com/code/jaejohn/answer-ladder-gemma-4-31b-on-all-five-rungs")]
src, out = Path(sys.argv[1]), Path(sys.argv[2])
text = src.read_text()
text = re.sub(r"\]\((figures/[^)]+)\)", lambda m: "](" + REPO + m.group(1) + ")", text)
out.write_text(text)
words = len(text.split())
print(f"wrote {out}: {words} words (limit 3,000); figures -> {REPO}figures/")
print("Project Links to paste:")
for name, url in LINKS:
    print(f"  {name}: {url}")
