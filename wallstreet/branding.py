"""README banner and GitHub social preview, in the 'Ledger' style.

Both are drawn as SVG from the real data (the Big Three's share of the US
market and its 2015-2025 line), then rendered to PNG so the fonts look the
same everywhere. Run `python assets/build.py` after the data changes.
"""

from __future__ import annotations

from html import escape

import bezel_charts as bc

from . import charts as C
from . import findings as F

BG, FG, SUB, BORDER = "#0E1120", "#F4F4F8", "#8C8AA0", "#2A2E44"
GRID = "#151A2E"
MONO = "DejaVu Sans Mono, ui-monospace, monospace"
DISPLAY = "Inter Display, Inter, system-ui, sans-serif"
BODY = "Inter, system-ui, sans-serif"
FIRMS = [
    ("JPMorgan", "jpmorgan"),
    ("Goldman Sachs", "goldman"),
    ("Morgan Stanley", "morgan_stanley"),
    ("BlackRock", "blackrock"),
    ("Vanguard", "vanguard"),
    ("State Street", "state_street"),
]


def accent() -> str:
    return bc.themes["dark"]["palette"][0]


def firm_colour(key: str) -> str:
    return bc.themes["dark"]["palette"][C.FIRM_COLOUR[key]]


def share_series() -> list[float]:
    share = F.big_three_market_share().sum(axis=1)
    return [float(v) * 100 for v in share[share.index.str.endswith("12-31")]]


def _text(x, y, s, size, fill, family=BODY, weight=400, spacing=0, anchor="start") -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
        f'letter-spacing="{spacing}" fill="{fill}" text-anchor="{anchor}">{escape(s)}</text>'
    )


def chips(x: float, y: float) -> str:
    out, cx, fund_x = [], x, x
    for i, (label, key) in enumerate(FIRMS):
        if i == 3:
            cx += 14
            fund_x = cx
        w = 34 + len(label) * 7.9
        out.append(
            f'<rect x="{cx:.0f}" y="{y}" width="{w:.0f}" height="30" rx="15" '
            f'fill="none" stroke="{BORDER}"/>'
            f'<circle cx="{cx + 15:.0f}" cy="{y + 15}" r="5" fill="{firm_colour(key)}"/>'
            + _text(f"{cx + 26:.0f}", y + 20, label, 14, FG, weight=500)
        )
        cx += w + 8
    out.append(_text(x, y - 12, "BANKS", 11, SUB, MONO, spacing=2))
    out.append(_text(f"{fund_x:.0f}", y - 12, "FUND MANAGERS", 11, SUB, MONO, spacing=2))
    return "".join(out)


def mini_chart(x0: float, y0: float, w: float, h: float) -> str:
    values = share_series()
    lo, hi = 10.0, 20.0
    pts = [
        (x0 + i * w / (len(values) - 1), y0 + h - (v - lo) / (hi - lo) * h)
        for i, v in enumerate(values)
    ]
    line = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    fill = line + f" L{x0 + w:.1f},{y0 + h} L{x0},{y0 + h} Z"
    a = accent()
    return (
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{a}" stop-opacity=".55"/>'
        f'<stop offset="1" stop-color="{a}" stop-opacity="0"/></linearGradient></defs>'
        f'<path d="{fill}" fill="url(#g)"/>'
        f'<path d="{line}" fill="none" stroke="{a}" stroke-width="3" stroke-linejoin="round"/>'
        f'<circle cx="{pts[-1][0]:.1f}" cy="{pts[-1][1]:.1f}" r="6" fill="{a}"/>'
        + _text(x0, y0 + h + 22, "2015", 12, SUB, MONO)
        + _text(x0 + w, y0 + h + 22, "2025", 12, SUB, MONO, anchor="end")
    )


def _frame(width: int, height: int, body: str, title: str) -> str:
    grid = "".join(
        f'<line x1="0" y1="{y}" x2="{width}" y2="{y}" stroke="{GRID}"/>'
        for y in range(0, height, 40)
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">'
        f'<title>{escape(title)}</title><rect width="{width}" height="{height}" fill="{BG}"/>'
        f"{grid}{body}</svg>"
    )


def headline() -> tuple[str, str]:
    n = F.headline_numbers()
    big = f"{n['big_three_share_2025'] * 100:.1f}%"
    return big, "of all US public company shares held by the Big Three"


def banner() -> str:
    big, caption = headline()
    body = (
        _text(64, 84, "SEC FILINGS · 2015–2025 · SCENARIOS TO 2035", 13, accent(), MONO, spacing=3)
        + _text(62, 160, "Wall Street", 68, FG, DISPLAY, 800)
        + _text(62, 232, "in Charts", 68, FG, DISPLAY, 800)
        + _text(66, 272, "Six giants · nine findings · 43 charts", 18, SUB)
        + chips(64, 322)
        + _text(840, 96, big, 56, FG, DISPLAY, 800)
        + _text(842, 124, caption, 15, SUB)
        + mini_chart(840, 150, 360, 150)
    )
    return _frame(1280, 400, body, f"Wall Street in Charts: {big} {caption}")


def social_preview() -> str:
    big, caption = headline()
    body = (
        _text(80, 112, "SEC FILINGS · 2015–2025 · SCENARIOS TO 2035", 15, accent(), MONO, spacing=3)
        + _text(76, 212, "Wall Street", 92, FG, DISPLAY, 800)
        + _text(76, 306, "in Charts", 92, FG, DISPLAY, 800)
        + _text(80, 356, "Six giants · nine findings · 43 charts", 22, SUB)
        + chips(80, 440)
        + _text(80, 560, "github.com/ShazMoghaddam/wall-street-in-charts", 15, SUB, MONO)
        + _text(80, 586, "Created by Shaz Moghaddam · London", 15, SUB, MONO)
        + _text(860, 150, big, 72, FG, DISPLAY, 800)
        + _text(862, 182, "of all US public company shares", 16, SUB)
        + _text(862, 204, "held by the Big Three", 16, SUB)
        + mini_chart(860, 250, 340, 240)
    )
    return _frame(1280, 640, body, f"Wall Street in Charts: {big} {caption}")
