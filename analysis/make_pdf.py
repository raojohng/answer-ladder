"""Render a paper version (Markdown with tables and figures) to PDF.
    <python with markdown + weasyprint> make_pdf.py paper_v<N>.md out.pdf      (run from paper_track/; figures resolve from here)"""
import sys
from pathlib import Path

import markdown
import weasyprint

src, out = Path(sys.argv[1]), Path(sys.argv[2])
import re
text = src.read_text()
# The availability paragraph as a short list (justified, its two lines stretch badly).
text = text.replace("Benchmark: kaggle.com/datasets/jaejohn/answer-ladder. Code, data, labels, scripts and `REPRODUCE.md`: github.com/raojohng/answer-ladder.",
                    "- Benchmark: kaggle.com/datasets/jaejohn/answer-ladder\n- Code, data, labels, scripts and `REPRODUCE.md`: github.com/raojohng/answer-ladder")
body = markdown.markdown(text, extensions=["tables", "sane_lists"])
# Kaggle and GitHub addresses become links (outside code spans).
body = re.sub(r"(?<![/\w>])((?:kaggle|github)\.com/[\w./-]*[\w/])", r'<a href="https://\1">\1</a>', body)
CSS = """
@page { size: A4; margin: 20mm 18mm 20mm 18mm;
        @bottom-center { content: counter(page); font: 9pt 'DejaVu Serif', serif; color: #555; } }
body { font: 10.2pt/1.45 'DejaVu Serif', 'Liberation Serif', serif; color: #111; }
h1 { font-size: 19pt; line-height: 1.2; margin: 0 0 4pt; text-align: center; }
h1 + h2 { font-size: 12.5pt; font-weight: normal; font-style: italic; text-align: center; margin: 0 0 14pt; border: none; }
h2 { font-size: 12.5pt; margin: 16pt 0 5pt; }
h3 { font-size: 11pt; margin: 12pt 0 4pt; }
p { margin: 0 0 7pt; text-align: justify; hyphens: auto; }
ul, ol { margin: 0 0 7pt 0; padding-left: 16pt; }
li { margin-bottom: 2pt; }
code { font: 8.6pt 'DejaVu Sans Mono', monospace; background: #f3f3f1; padding: 0 2pt; border-radius: 2pt; }
table { border-collapse: collapse; width: 100%; margin: 4pt 0 10pt; font-size: 8.4pt; line-height: 1.3; page-break-inside: avoid; }
th, td { border-top: 0.5pt solid #bbb; border-bottom: 0.5pt solid #bbb; padding: 3pt 4pt; text-align: left; vertical-align: top; }
th { background: #f1f1ee; font-weight: bold; }
p:has(+ table) { break-after: avoid; }
table + p { break-before: avoid; }
a { color: #1a4f8f; text-decoration: none; }
img { display: block; max-width: 100%; margin: 6pt auto 2pt; page-break-inside: avoid; }
p:has(> img) { text-align: center; }
"""
html = f"<!doctype html><html><head><meta charset='utf-8'><title>{src.stem}</title><style>{CSS}</style></head><body>{body}</body></html>"
weasyprint.HTML(string=html, base_url=str(src.resolve().parent)).write_pdf(out)
print("wrote", out)
