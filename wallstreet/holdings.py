"""Full 13F holdings for the Big Three, read back from the download cache.

Stage 1 kept only the top 500 holdings per quarter in data/processed/. The
sector, energy and ownership findings need every position, so this module
re-reads the cached filings (data/raw/) and keeps share positions only.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from . import thirteenf
from .config import Settings
from .http import Fetcher

FUND_MANAGERS = ("blackrock", "vanguard", "state_street")


def firm_quarter(fetcher: Fetcher, parts: list) -> pd.DataFrame:
    rows = pd.concat(
        [
            thirteenf.parse_info_table(
                fetcher.get_bytes(thirteenf.info_table_url(fetcher, f)), f.filed
            )
            for f in parts
        ],
        ignore_index=True,
    )
    rows = rows[rows["share_type"] == "SH"]
    return (
        rows.groupby("cusip", as_index=False)
        .agg(
            issuer=("issuer", "first"),
            title_of_class=("title_of_class", "first"),
            value_usd=("value_usd", "sum"),
            shares=("shares", "sum"),
        )
        .sort_values("value_usd", ascending=False)
    )


def full_holdings(
    fetcher: Fetcher, settings: Settings, quarter_ends: list[date] | None = None
) -> pd.DataFrame:
    """Every share position for each fund manager and quarter end."""
    frames = []
    for key in FUND_MANAGERS:
        firm = settings.firms[key]
        filings = thirteenf.firm_quarterly_filings(fetcher, firm, settings.start, settings.end)
        for q, parts in filings.items():
            if quarter_ends is not None and q not in quarter_ends:
                continue
            df = firm_quarter(fetcher, parts)
            df.insert(0, "quarter_end", q.isoformat())
            df.insert(0, "firm", key)
            frames.append(df)
    return pd.concat(frames, ignore_index=True)


def reference_prices(full: pd.DataFrame, quarter_end: str) -> pd.Series:
    """Value per share by CUSIP: the median across the Big Three's filings."""
    df = full[(full["quarter_end"] == quarter_end) & (full["shares"] > 0)]
    return (df["value_usd"] / df["shares"]).groupby(df["cusip"]).median()


def largest_position(full: pd.DataFrame, quarter_end: str) -> pd.Series:
    """The biggest Big Three holding (shares) in each CUSIP."""
    df = full[full["quarter_end"] == quarter_end]
    return df.groupby("cusip")["shares"].max()
