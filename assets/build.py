"""Build the README banner and the GitHub social preview.

Usage (from the repo root, needs rsvg-convert, e.g. `brew install librsvg`):

    python assets/build.py

Writes assets/banner.svg and .png (shown in the README), and
assets/social-preview.svg and .png (upload the PNG in the repo's Settings,
under "Social preview"). PNGs keep the fonts looking the same everywhere.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from wallstreet import branding  # noqa: E402

OUT = ROOT / "assets"


def render(svg: Path, png: Path, zoom: float) -> None:
    tool = shutil.which("rsvg-convert")
    if not tool:
        raise SystemExit("rsvg-convert not found. On a Mac: brew install librsvg")
    subprocess.run([tool, "-z", str(zoom), str(svg), "-o", str(png)], check=True)


def main() -> None:
    for name, svg, zoom in (
        ("banner", branding.banner(), 2),  # 2560 x 800, crisp on high-density screens
        ("social-preview", branding.social_preview(), 1),  # 1280 x 640, GitHub's size
    ):
        path = OUT / f"{name}.svg"
        path.write_text(svg)
        render(path, OUT / f"{name}.png", zoom)
        print(f"wrote assets/{name}.svg and .png")


if __name__ == "__main__":
    main()
