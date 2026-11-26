"""13F holdings for BlackRock, Vanguard and State Street.

A 13F-HR lists a manager's US-listed shares (and some other "13(f)
securities") at each quarter end. Things worth knowing:

- Value units changed. Filings made before 3 January 2023 report value in
  thousands of dollars; later filings use whole dollars. We store dollars.
- Options rows (put/call) are dropped: they are not shareholdings.
- One security can appear on many rows (one per sub-manager); we add them up
  by CUSIP so each security appears once per filer and quarter.
- Amendments come in two kinds. A RESTATEMENT replaces the whole report, so
  we use it instead of the original (State Street's Q3 2016 report grew from
  $0.78 trillion to $0.99 trillion this way). A NEW HOLDINGS amendment only
  adds a few late lines, so we leave those out.
"""

from __future__ import annotations

import re
from datetime import date

import pandas as pd
from lxml import etree

from .config import Firm
from .edgar import Filing, folder_files, list_filings
from .http import Fetcher

VALUE_IN_DOLLARS_FROM = date(2023, 1, 3)
COLUMNS = ["cusip", "issuer", "title_of_class", "value_usd", "shares", "share_type"]


def quarterly_filings(
    fetcher: Fetcher, ciks: tuple[int, ...], start: date, end: date
) -> dict[date, Filing]:
    """The 13F-HR for each quarter end, across one or more filer IDs.

    When a firm has changed ID (BlackRock), the newest filing for a quarter wins.
    """
    chosen: dict[date, Filing] = {}
    for cik in ciks:
        for f in list_filings(fetcher, cik, {"13F-HR", "13F-HR/A"}, since=start):
            if f.report_date is None or not (start <= f.report_date <= end):
                continue
            if f.form == "13F-HR/A" and amendment_type(fetcher, f) != "RESTATEMENT":
                continue
            current = chosen.get(f.report_date)
            if current is None or _rank(f) > _rank(current):
                chosen[f.report_date] = f
    return dict(sorted(chosen.items()))


def _rank(f: Filing) -> tuple[int, date]:
    """A restatement beats the original; otherwise the newest filing wins."""
    return (1 if f.form == "13F-HR/A" else 0, f.filed)


def amendment_type(fetcher: Fetcher, filing: Filing) -> str:
    """RESTATEMENT (replaces the report) or NEW HOLDINGS (adds a few late lines)."""
    cover = fetcher.get_bytes(filing.folder_url + "primary_doc.xml")
    match = re.search(rb"<(?:\w+:)?amendmentType>\s*([^<]+?)\s*<", cover)
    return match.group(1).decode().upper() if match else ""


def firm_quarterly_filings(
    fetcher: Fetcher, firm: Firm, start: date, end: date
) -> dict[date, list[Filing]]:
    """Every filing that makes up a firm's holdings in each quarter.

    Usually one filing. For BlackRock up to Q4 2016 it is the parent filing plus
    the separate filings of its main subsidiaries, which we add together.
    """
    out = {q: [f] for q, f in quarterly_filings(fetcher, firm.thirteenf_cik, start, end).items()}
    if firm.thirteenf_parts_cik and firm.thirteenf_parts_until:
        until = min(end, firm.thirteenf_parts_until)
        for cik in firm.thirteenf_parts_cik:
            for q, f in quarterly_filings(fetcher, (cik,), start, until).items():
                out.setdefault(q, []).append(f)
    return dict(sorted(out.items()))


def info_table_url(fetcher: Fetcher, filing: Filing) -> str:
    """The holdings table is the largest XML file that is not primary_doc.xml."""
    xmls = [
        f
        for f in folder_files(fetcher, filing)
        if f["name"].lower().endswith(".xml") and f["name"].lower() != "primary_doc.xml"
    ]
    if not xmls:
        raise ValueError(f"No information table in {filing.accn}")
    best = max(xmls, key=lambda f: f["size"])
    return filing.folder_url + best["name"]


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_info_table(xml: bytes, filed: date) -> pd.DataFrame:
    """Parse a 13F information table into one row per holding (dollars)."""
    multiplier = 1 if filed >= VALUE_IN_DOLLARS_FROM else 1000
    rows = []
    parser = etree.XMLParser(huge_tree=True, recover=True, resolve_entities=False, no_network=True)
    root = etree.fromstring(xml, parser=parser)
    for node in root.iter():
        if not isinstance(node.tag, str) or _local(node.tag) != "infoTable":
            continue
        rec: dict[str, str] = {}
        for child in node.iter():
            if isinstance(child.tag, str) and child.text and child.text.strip():
                rec[_local(child.tag)] = child.text.strip()
        if rec.get("putCall"):
            continue
        rows.append(
            {
                "cusip": rec.get("cusip", "").upper(),
                "issuer": rec.get("nameOfIssuer", ""),
                "title_of_class": rec.get("titleOfClass", ""),
                "value_usd": float(rec.get("value", 0) or 0) * multiplier,
                "shares": float(rec.get("sshPrnamt", 0) or 0),
                "share_type": rec.get("sshPrnamtType", ""),
            }
        )
    return pd.DataFrame(rows, columns=COLUMNS)


def aggregate_by_security(holdings: pd.DataFrame) -> pd.DataFrame:
    """One row per CUSIP: values and shares summed across sub-managers."""
    if holdings.empty:
        return holdings
    return (
        holdings.groupby("cusip", as_index=False)
        .agg(
            issuer=("issuer", "first"),
            title_of_class=("title_of_class", "first"),
            value_usd=("value_usd", "sum"),
            shares=("shares", "sum"),
        )
        .sort_values("value_usd", ascending=False)
        .reset_index(drop=True)
    )


def summarise(
    firm: str, quarter_end: date, filings: list[Filing], securities: pd.DataFrame, top_n: int
) -> tuple[pd.DataFrame, dict]:
    """Top-N holdings plus a totals row so coverage can always be stated."""
    total = float(securities["value_usd"].sum())
    top = securities.head(top_n).copy()
    top.insert(0, "rank", range(1, len(top) + 1))
    top.insert(0, "quarter_end", quarter_end.isoformat())
    top.insert(0, "firm", firm)
    top["weight"] = top["value_usd"] / total if total else 0.0
    totals = {
        "firm": firm,
        "quarter_end": quarter_end.isoformat(),
        "filings": len(filings),
        "accn": ";".join(f.accn for f in filings),
        "filer_cik": ";".join(str(f.cik) for f in filings),
        "filed": max(f.filed for f in filings).isoformat(),
        "total_value_usd": total,
        "positions": int(len(securities)),
        f"top{top_n}_value_usd": float(top["value_usd"].sum()),
        f"top{top_n}_share": float(top["value_usd"].sum() / total) if total else 0.0,
    }
    return top, totals
