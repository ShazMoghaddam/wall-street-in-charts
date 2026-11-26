"""The report site in docs/: complete, self-consistent and accessible basics."""

import re

import pytest

from wallstreet.config import ROOT

DOCS = ROOT / "docs"
INDEX = DOCS / "index.html"

if not INDEX.exists():
    pytest.skip("site not built", allow_module_level=True)

HTML = INDEX.read_text()


def test_all_nine_findings_and_method():
    for n in range(1, 10):
        assert f'id="finding-{n}"' in HTML
        assert f'href="#finding-{n}"' in HTML
    assert 'id="method"' in HTML


def test_every_chart_file_exists():
    srcs = re.findall(r'(?:src|srcset)="(charts/[^"]+)"', HTML)
    assert len(srcs) > 80
    missing = [s for s in srcs if not (DOCS / s).exists()]
    assert not missing


def test_every_image_has_alt_text():
    imgs = re.findall(r"<img [^>]*>", HTML)
    assert imgs
    assert all(re.search(r'alt="[^"]{10,}"', i) for i in imgs)


def test_accessibility_basics():
    assert '<html lang="en">' in HTML
    assert 'class="skip"' in HTML
    assert 'aria-label="Contents"' in HTML
    assert HTML.count("<h1") == 1


def test_sharing_tags():
    assert 'property="og:image"' in HTML
    assert (DOCS / "social-preview.png").exists()
    assert (DOCS / ".nojekyll").exists()


def test_not_financial_advice_is_stated():
    assert HTML.count("Not financial advice") >= 2


def test_headline_numbers_match_readme():
    readme = (ROOT / "README.md").read_text()
    share = re.search(r"held (\d+\.\d)% of all US public company shares", readme).group(1)
    assert f"{share}%" in HTML
