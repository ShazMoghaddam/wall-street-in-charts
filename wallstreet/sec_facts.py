"""Quarterly revenue, profit and total assets from SEC XBRL company facts.

Two traps this module handles:

1. Companies rarely report Q4 on its own. The 10-K gives the full year, so Q4
   is the full year minus Q1 to Q3 (or minus the nine-month year-to-date figure).
2. Firms use different tags for the same idea (for example "Revenues" vs
   "RevenuesNetOfInterestExpense"). Each firm has a tag priority list in
   data/firms.yaml; for every quarter the first tag with a value wins.

All five listed firms have a December year end, which the code checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from .config import Firm
from .http import Fetcher

FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A"}

QUARTER_DAYS = (80, 100)
NINE_MONTH_DAYS = (260, 285)
YEAR_DAYS = (350, 380)

DURATION_METRICS = {
    "net_income": ("NetIncomeLoss",),
    # Interest earned minus interest paid. Banks and State Street only:
    # BlackRock does not report it.
    "net_interest_income": ("InterestIncomeExpenseNet",),
}
INSTANT_METRICS = {"total_assets": ("Assets",)}


@dataclass(frozen=True)
class Fact:
    tag: str
    start: date | None
    end: date
    value: float
    accn: str
    form: str
    filed: date

    @property
    def days(self) -> int | None:
        return None if self.start is None else (self.end - self.start).days + 1


def fetch_company_facts(fetcher: Fetcher, firm: Firm) -> list[dict]:
    return [fetcher.get_json(FACTS_URL.format(cik=cik)) for cik in firm.cik]


def extract_facts(company_facts: list[dict], tag: str) -> list[Fact]:
    """All USD facts for a tag from 10-K/10-Q filings, latest filing per period.

    Taking the latest filing means restated figures replace the originals.
    """
    best: dict[tuple, Fact] = {}
    for doc in company_facts:
        units = doc.get("facts", {}).get("us-gaap", {}).get(tag, {}).get("units", {})
        for row in units.get("USD", []):
            if row.get("form") not in FORMS:
                continue
            fact = Fact(
                tag=tag,
                start=date.fromisoformat(row["start"]) if row.get("start") else None,
                end=date.fromisoformat(row["end"]),
                value=float(row["val"]),
                accn=row["accn"],
                form=row["form"],
                filed=date.fromisoformat(row["filed"]),
            )
            key = (fact.start, fact.end)
            if key not in best or fact.filed > best[key].filed:
                best[key] = fact
    return sorted(best.values(), key=lambda f: (f.end, f.start or f.end))


def quarter_label(d: date) -> str:
    return f"{d.year}Q{(d.month - 1) // 3 + 1}"


def is_quarter_end(d: date) -> bool:
    return (d.month, d.day) in {(3, 31), (6, 30), (9, 30), (12, 31)}


def _in(days: int | None, bounds: tuple[int, int]) -> bool:
    return days is not None and bounds[0] <= days <= bounds[1]


def discrete_quarters(facts: list[Fact]) -> pd.DataFrame:
    """Turn duration facts into one value per calendar quarter.

    Reported three-month values are used as they are. A missing quarter is
    derived from the full year (minus the other three quarters) or from the
    nine-month year-to-date value (for Q4).
    """
    rows: dict[str, dict] = {}
    for f in facts:
        if _in(f.days, QUARTER_DAYS) and is_quarter_end(f.end):
            rows[quarter_label(f.end)] = _row(f, f.value, "reported")

    years = [f for f in facts if _in(f.days, YEAR_DAYS) and (f.end.month, f.end.day) == (12, 31)]
    nine_months = {
        f.end.year: f
        for f in facts
        if _in(f.days, NINE_MONTH_DAYS) and (f.end.month, f.end.day) == (9, 30)
    }
    for fy in years:
        year = fy.end.year
        labels = [f"{year}Q{q}" for q in range(1, 5)]
        missing = [lbl for lbl in labels if lbl not in rows]
        if len(missing) == 1:
            known = sum(rows[lbl]["value"] for lbl in labels if lbl != missing[0])
            rows[missing[0]] = _row(fy, fy.value - known, "derived_from_full_year", missing[0])
        elif f"{year}Q4" in missing and year in nine_months:
            value = fy.value - nine_months[year].value
            rows[f"{year}Q4"] = _row(fy, value, "derived_from_nine_months", f"{year}Q4")
    if not rows:
        return pd.DataFrame(columns=["quarter", "value", "tag", "method", "accn", "filed"])
    return pd.DataFrame(rows.values()).sort_values("quarter").reset_index(drop=True)


def instant_quarters(facts: list[Fact]) -> pd.DataFrame:
    rows = {
        quarter_label(f.end): _row(f, f.value, "reported")
        for f in facts
        if f.start is None and is_quarter_end(f.end)
    }
    if not rows:
        return pd.DataFrame(columns=["quarter", "value", "tag", "method", "accn", "filed"])
    return pd.DataFrame(rows.values()).sort_values("quarter").reset_index(drop=True)


def _row(f: Fact, value: float, method: str, label: str | None = None) -> dict:
    return {
        "quarter": label or quarter_label(f.end),
        "value": value,
        "tag": f.tag,
        "method": method,
        "accn": f.accn,
        "filed": f.filed.isoformat(),
    }


def coalesce(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """First frame with a value for a quarter wins (frames in tag priority order)."""
    out: dict[str, dict] = {}
    for frame in frames:
        for row in frame.to_dict("records"):
            out.setdefault(row["quarter"], row)
    if not out:
        return pd.DataFrame(columns=["quarter", "value", "tag", "method", "accn", "filed"])
    return pd.DataFrame(out.values()).sort_values("quarter").reset_index(drop=True)


def firm_fundamentals(company_facts: list[dict], firm: Firm) -> pd.DataFrame:
    metrics: dict[str, pd.DataFrame] = {}
    metrics["revenue"] = coalesce(
        [discrete_quarters(extract_facts(company_facts, t)) for t in firm.revenue_tags]
    )
    for name, tags in DURATION_METRICS.items():
        metrics[name] = coalesce([discrete_quarters(extract_facts(company_facts, t)) for t in tags])
    for name, tags in INSTANT_METRICS.items():
        metrics[name] = coalesce([instant_quarters(extract_facts(company_facts, t)) for t in tags])

    frames = []
    for name, frame in metrics.items():
        frame = frame.copy()
        frame.insert(0, "metric", name)
        frame.insert(0, "firm", firm.key)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def tag_overlap(company_facts: list[dict], tags: tuple[str, ...]) -> pd.DataFrame:
    """Quarters where two revenue tags both have values, to check they agree."""
    per_tag = {t: discrete_quarters(extract_facts(company_facts, t)) for t in tags}
    rows = []
    for i, a in enumerate(tags):
        for b in tags[i + 1 :]:
            merged = per_tag[a].merge(per_tag[b], on="quarter", suffixes=("_a", "_b"))
            for r in merged.itertuples():
                rows.append(
                    {"tag_a": a, "tag_b": b, "quarter": r.quarter, "a": r.value_a, "b": r.value_b}
                )
    return pd.DataFrame(rows)
