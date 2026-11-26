"""The GitHub Pages report: one long page built from the findings pages.

findings/build.py calls build() after writing the findings, so the site
always matches them. Output goes to docs/ (served by GitHub Pages):
docs/index.html, docs/charts/*.svg and docs/social-preview.png. The page
layout and styles live in templates/report.html.
"""

from __future__ import annotations

import re
import shutil
from html import escape
from pathlib import Path

import markdown

from .config import ROOT

DOCS = ROOT / "docs"
TEMPLATE = Path(__file__).parent / "templates" / "report.html"
REPO = "https://github.com/ShazMoghaddam/wall-street-in-charts"
SITE = "https://shazmoghaddam.github.io/wall-street-in-charts/"
WEBSITE = "https://shazmoghaddam.github.io/"
LINKEDIN = "https://www.linkedin.com/in/shazmoghaddam/"


def section_html(number: int, md_text: str) -> tuple[str, str]:
    """Markdown page -> (title, <section> HTML) with headings stepped down one level."""
    lines = md_text.splitlines()
    title = re.sub(r"^#\s*\d+\.\s*", "", lines[0]).strip()
    body = "\n".join(lines[1:])
    body = re.sub(r"^## ", "### ", body, flags=re.M)
    # Repo paths in code spans become links to the file on GitHub.
    html = markdown.markdown(body, extensions=["tables"])
    html = re.sub(
        r"<code>((?:data|models|wallstreet|findings)/[^<\s]+)</code>",
        lambda m: f'<a href="{REPO}/blob/main/{m.group(1)}"><code>{m.group(1)}</code></a>',
        html,
    )
    sid = f"finding-{number}"
    section = (
        f'<section id="{sid}" aria-labelledby="{sid}-title">'
        f'<p class="kicker">Finding {number}</p>'
        f'<h2 id="{sid}-title">{escape(title)}</h2>{html}</section>'
    )
    return title, section


def stat(big: str, label: str, colour: str) -> str:
    return (
        f'<div class="stat" style="--c:{colour}"><span class="big">{escape(big)}</span>'
        f"<span>{escape(label)}</span></div>"
    )


def build(
    pages: list[tuple[int, str]], stats: list[tuple[str, str, str]], description: str
) -> None:
    """pages: (finding number, markdown with charts/ paths). stats: (big, label, colour)."""
    DOCS.mkdir(exist_ok=True)
    charts_out = DOCS / "charts"
    if charts_out.exists():
        shutil.rmtree(charts_out)
    shutil.copytree(ROOT / "charts", charts_out)
    shutil.copy(ROOT / "assets" / "social-preview.png", DOCS / "social-preview.png")
    (DOCS / ".nojekyll").write_text("")

    sections, nav = [], []
    for number, md_text in sorted(pages):
        title, html = section_html(number, md_text)
        sections.append(html)
        nav.append(f'<li><a href="#finding-{number}"><span>{number}</span>{escape(title)}</a></li>')
    nav.append('<li><a href="#method"><span>·</span>Data and method</a></li>')

    page = TEMPLATE.read_text().format(
        description=escape(description),
        site=SITE,
        repo=REPO,
        website=WEBSITE,
        linkedin=LINKEDIN,
        stats="".join(stat(*s) for s in stats),
        nav="".join(nav),
        sections="".join(sections),
    )
    (DOCS / "index.html").write_text(page)
