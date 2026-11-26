"""Bank segment revenue and profit from 10-K XBRL instance documents.

Segment figures are not in the SEC company facts API because they carry an
extra "dimension" (the business segment). So we read each bank's 10-K XBRL
instance and keep facts that:

- use a revenue or profit tag we care about,
- cover a full calendar year,
- have exactly one dimension: the business-segment axis.

Segment names change over time (Goldman reorganised in 2020 and 2022), so
the raw member names are kept here. data/manual/segment_map.csv maps them to
the report's buckets in a later step.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
from lxml import etree

from .edgar import Filing, folder_files
from .http import Fetcher

SEGMENT_AXIS = "us-gaap:StatementBusinessSegmentsAxis"
_PRE_TAX = "IncomeLossFromContinuingOperationsBeforeIncomeTaxes"
TAGS = {
    "RevenuesNetOfInterestExpense": "revenue",
    "Revenues": "revenue",
    "NetIncomeLoss": "net_income",
    _PRE_TAX + "ExtraordinaryItemsNoncontrollingInterest": "pre_tax_income",
    _PRE_TAX + "MinorityInterestAndIncomeLossFromEquityMethodInvestments": "pre_tax_income",
}
SKIP_SUFFIXES = ("_cal.xml", "_def.xml", "_lab.xml", "_pre.xml")
XBRLI = "http://www.xbrl.org/2003/instance"
XBRLDI = "http://xbrl.org/2006/xbrldi"


def instance_url(fetcher: Fetcher, filing: Filing) -> str:
    xmls = [
        f["name"]
        for f in folder_files(fetcher, filing)
        if f["name"].endswith(".xml")
        and not f["name"].endswith(SKIP_SUFFIXES)
        and f["name"] not in ("FilingSummary.xml", "primary_doc.xml")
    ]
    if not xmls:
        raise ValueError(f"No XBRL instance in {filing.accn}")
    preferred = [n for n in xmls if n.endswith("_htm.xml")] or xmls
    return filing.folder_url + preferred[0]


def segment_member(members: list[tuple[str, str]]) -> str | None:
    """The segment for a context, or None if it is not a plain segment total.

    Accepted: the segment axis alone (older filings), or the segment axis plus
    "operating segments" on the consolidation-items axis (newer filings).
    Anything else (regions, eliminations, parent company) is skipped.
    """
    dims = dict(members)
    if len(dims) != len(members) or SEGMENT_AXIS not in dims:
        return None
    others = {k: v for k, v in dims.items() if k != SEGMENT_AXIS}
    if not others:
        return dims[SEGMENT_AXIS]
    if len(others) == 1:
        axis, value = next(iter(others.items()))
        if axis.endswith(":ConsolidationItemsAxis") and value.endswith(":OperatingSegmentsMember"):
            return dims[SEGMENT_AXIS]
    return None


def _contexts(root: etree._Element) -> dict[str, dict]:
    out = {}
    for ctx in root.iter(f"{{{XBRLI}}}context"):
        start = ctx.find(f".//{{{XBRLI}}}startDate")
        end = ctx.find(f".//{{{XBRLI}}}endDate")
        if start is None or end is None:
            continue
        members = [
            (m.get("dimension"), (m.text or "").strip())
            for m in ctx.iter(f"{{{XBRLDI}}}explicitMember")
        ]
        typed = list(ctx.iter(f"{{{XBRLDI}}}typedMember"))
        out[ctx.get("id")] = {
            "start": date.fromisoformat(start.text.strip()[:10]),
            "end": date.fromisoformat(end.text.strip()[:10]),
            "members": members,
            "typed": bool(typed),
        }
    return out


def parse_segments(xml: bytes, firm: str, filing: Filing) -> pd.DataFrame:
    parser = etree.XMLParser(huge_tree=True, recover=True, resolve_entities=False, no_network=True)
    root = etree.fromstring(xml, parser=parser)
    contexts = _contexts(root)
    nsmap = {v: k for k, v in root.nsmap.items() if k}
    rows = []
    for el in root.iter():
        if not isinstance(el.tag, str) or "}" not in el.tag:
            continue
        ns, local = el.tag[1:].split("}", 1)
        if local not in TAGS or nsmap.get(ns) != "us-gaap":
            continue
        ctx = contexts.get(el.get("contextRef"))
        if not ctx or ctx["typed"]:
            continue
        member = segment_member(ctx["members"])
        if member is None:
            continue
        days = (ctx["end"] - ctx["start"]).days + 1
        if not (350 <= days <= 380) or (ctx["end"].month, ctx["end"].day) != (12, 31):
            continue
        text = (el.text or "").strip()
        if not text:
            continue
        rows.append(
            {
                "firm": firm,
                "year": ctx["end"].year,
                "segment_member": member.split(":", 1)[-1],
                "metric": TAGS[local],
                "tag": local,
                "value_usd": float(text),
                "accn": filing.accn,
                "report_year": filing.report_date.year if filing.report_date else None,
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # One value per year/segment/metric: prefer the first tag in TAGS order.
    order = {t: i for i, t in enumerate(TAGS)}
    df["_order"] = df["tag"].map(order)
    df = df.sort_values("_order").drop_duplicates(["year", "segment_member", "metric"])
    return df.drop(columns="_order").sort_values(["year", "metric", "segment_member"])


def latest_per_year(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Each 10-K repeats prior years; keep the figure from the newest 10-K.

    Newer filings carry restated figures that match the current segment set
    for the years they cover, which keeps each year internally consistent.
    """
    df = pd.concat([f for f in frames if not f.empty], ignore_index=True)
    df = df.sort_values("report_year", ascending=False)
    newest_for_year = df.groupby(["firm", "year"])["report_year"].transform("max")
    df = df[df["report_year"] == newest_for_year]
    return df.sort_values(["firm", "year", "metric", "segment_member"]).reset_index(drop=True)
