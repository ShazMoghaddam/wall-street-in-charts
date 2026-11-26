"""Assets under management (AUM) for BlackRock and State Street.

AUM is the money a fund manager looks after for clients. It is not tagged in
XBRL, so we read it from each quarterly earnings press release (the 8-K with
Item 2.02) filed with the SEC:

- look for "assets under management" or "AUM" in the release text,
- take the first number in the expected range just after it
  (BlackRock reports in $ millions, State Street in $ billions),
- assign it to the quarter that ended just before the release was filed.

Every row keeps the SEC accession number, so each figure can be checked.
Vanguard is private and files no results, so its AUM is entered by hand in
data/manual/vanguard_aum.csv from Vanguard's own published figures.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from .edgar import Filing, folder_files, list_filings
from .http import Fetcher

KEYWORD = re.compile(r"assets under management|\bAUM\b", re.I)
NUMBER = re.compile(r"\$?\s?(\d{1,3}(?:,\d{3})+(?:\.\d+)?)")
MAX_DAYS_AFTER_QUARTER = 60
SEARCH_WINDOW = 200


@dataclass(frozen=True)
class AumRule:
    low: float  # plausible range in the release's own unit
    high: float
    to_trillions: float  # divide by this to get $ trillions


RULES = {
    "blackrock": AumRule(low=3e6, high=3e7, to_trillions=1e6),  # $ millions
    "state_street": AumRule(low=1_500, high=9_000, to_trillions=1e3),  # $ billions
}


def clean_text(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text)


def find_aum(text: str, rule: AumRule) -> float | None:
    """First plausible AUM figure after an AUM keyword, in $ trillions."""
    for kw in KEYWORD.finditer(text):
        window = text[kw.end() : kw.end() + SEARCH_WINDOW]
        for n in NUMBER.finditer(window):
            value = float(n.group(1).replace(",", ""))
            if rule.low <= value <= rule.high:
                return value / rule.to_trillions
    return None


def previous_quarter_end(d: date) -> date:
    q_month = ((d.month - 1) // 3) * 3  # 0, 3, 6, 9
    if q_month == 0:
        return date(d.year - 1, 12, 31)
    return date(d.year, q_month + 1, 1) - timedelta(days=1)


def exhibit_names(fetcher: Fetcher, filing: Filing) -> list[str]:
    """Press-release exhibits first (99.1, 'earnings'), then any other HTML."""
    names = [
        f["name"]
        for f in folder_files(fetcher, filing)
        if f["name"].lower().endswith((".htm", ".html"))
        and f["name"] != filing.primary_document
        and "index" not in f["name"].lower()
    ]

    def score(name: str) -> int:
        n = name.lower()
        if re.search(r"ex-?99[._-]?1|991", n) or "earningspre" in n or "pressrelease" in n:
            return 0
        if "99" in n:
            return 1
        return 2

    return sorted(names, key=score)


def firm_aum(
    fetcher: Fetcher, firm: str, ciks: tuple[int, ...], start: date, end: date
) -> pd.DataFrame:
    rule = RULES[firm]
    by_quarter: dict[date, dict] = {}
    releases = []
    for cik in ciks:
        filings = list_filings(fetcher, cik, {"8-K"}, since=start)
        releases += [f for f in filings if "2.02" in f.items]
    seen: set[date] = set()
    for filing in sorted(releases, key=lambda f: f.filed):
        quarter_end = previous_quarter_end(filing.filed)
        if not (start <= quarter_end <= end) or quarter_end in seen:
            continue
        if (filing.filed - quarter_end).days > MAX_DAYS_AFTER_QUARTER:
            continue
        # Only the first results filing after a quarter end is the earnings
        # release. Later 2.02 filings (conference decks) are ignored.
        seen.add(quarter_end)
        for name in exhibit_names(fetcher, filing):
            value = find_aum(clean_text(fetcher.get_text(filing.folder_url + name)), rule)
            if value is not None:
                by_quarter[quarter_end] = {
                    "firm": firm,
                    "quarter_end": quarter_end.isoformat(),
                    "aum_trillion_usd": round(value, 6),
                    "source": "SEC 8-K earnings release",
                    "accn": filing.accn,
                    "document": name,
                }
                break
    return pd.DataFrame(by_quarter.values())
