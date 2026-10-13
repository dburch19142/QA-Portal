"""Builds index.html, the standalone site, from qa-portfolio-tracker.html.

The tracker file is the source published as a Claude artifact, which supplies
its own document shell. A plain web host needs a full HTML document, so this
wraps the same markup, styles and script in one.

    python build.py
"""
from pathlib import Path

ROOT = Path(__file__).parent
SOURCE = ROOT / "qa-portfolio-tracker.html"
BODY_STARTS = '<div class="app">'

HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="description" content="QA portal tracking test cases, bug reports, Playwright runs, API checks and README progress across projects.">
<style>body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>
"""


def render() -> str:
    source = SOURCE.read_text(encoding="utf-8")
    head, body = source.split(BODY_STARTS, 1)
    return f"{HEAD}{head.strip()}\n</head>\n<body>\n{BODY_STARTS}{body.rstrip()}\n</body>\n</html>\n"


def build() -> None:
    (ROOT / "index.html").write_text(render(), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    build()
