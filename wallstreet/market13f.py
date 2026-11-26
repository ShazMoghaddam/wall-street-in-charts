"""The 'market' for finding 4: every 13F filer's holdings added up.

The SEC publishes all 13F filings as quarterly bulk data sets, grouped by
filing date. Year-end holdings are filed in January and February, so for
each year-end we read the data set that covers those months, keep original
13F-HR reports for 31 December, drop options, and add up value by CUSIP.

This is the institutional market (managers with over $100m in US-listed
shares), not literally every share. Amendments are left out.

Unit slips: some filers report dollars where the rules asked for thousands
(or the reverse), so a position can be 1,000 times too big or too small. We
check every row's value per share against a reference price for that CUSIP
from the BlackRock, Vanguard and State Street filings (already checked in
stage 1), and keep whichever of x1, /1000 or x1000 lands closest. Rows still
more than 25% off that price, rows claiming more than 3 times the largest
Big Three position in the same stock, rows for securities the Big Three
don't hold, and non-share rows (bond principal amounts) are left out. The
counts of fixed and dropped rows are reported.
"""

from __future__ import annotations

import io
import zipfile
from datetime import date

import numpy as np
import pandas as pd

from .http import Fetcher

BASE = "https://www.sec.gov/files/structureddata/data/form-13f-data-sets/"
VALUE_IN_DOLLARS_FROM = pd.Timestamp("2023-01-03")


def dataset_for_year_end(year: int) -> str:
    """The bulk file whose filing window holds most 31 December reports."""
    if year <= 2022:
        return f"{year + 1}q1_form13f.zip"
    special = {
        2023: "01jan2024-29feb2024_form13f.zip",
        2024: "01dec2024-28feb2025_form13f.zip",
        2025: "01dec2025-28feb2026_form13f.zip",
    }
    return special[year]


def _read(z: zipfile.ZipFile, name: str, cols: list[str]) -> pd.DataFrame:
    with z.open(name) as f:
        return pd.read_csv(
            io.TextIOWrapper(f, encoding="utf-8", errors="replace"),
            sep="\t",
            usecols=cols,
            dtype=str,
            quoting=3,
            on_bad_lines="skip",
        )


PRICE_TOLERANCE = 1.25
MAX_SHARES_VS_BIG_THREE = 3


def market_holdings(
    fetcher: Fetcher, year: int, ref_price: pd.Series, ref_shares: pd.Series
) -> tuple[pd.DataFrame, dict]:
    """One row per CUSIP with summed value (dollars), plus a summary dict.

    ref_price: value per share by CUSIP from the Big Three at this year-end.
    ref_shares: the largest Big Three position (shares) in each CUSIP.
    """
    raw = fetcher.get_bytes(BASE + dataset_for_year_end(year))
    z = zipfile.ZipFile(io.BytesIO(raw))
    subs = _read(
        z, "SUBMISSION.tsv", ["ACCESSION_NUMBER", "FILING_DATE", "SUBMISSIONTYPE", "PERIODOFREPORT"]
    )
    period = pd.to_datetime(subs["PERIODOFREPORT"], format="%d-%b-%Y", errors="coerce")
    subs = subs[(subs["SUBMISSIONTYPE"] == "13F-HR") & (period == pd.Timestamp(date(year, 12, 31)))]
    filed = pd.to_datetime(subs["FILING_DATE"], format="%d-%b-%Y", errors="coerce")
    mult = dict(
        zip(
            subs["ACCESSION_NUMBER"],
            (filed < VALUE_IN_DOLLARS_FROM).map({True: 1000.0, False: 1.0}),
            strict=True,
        )
    )

    info = _read(
        z,
        "INFOTABLE.tsv",
        [
            "ACCESSION_NUMBER",
            "NAMEOFISSUER",
            "TITLEOFCLASS",
            "CUSIP",
            "VALUE",
            "SSHPRNAMT",
            "SSHPRNAMTTYPE",
            "PUTCALL",
        ],
    )
    info = info[info["ACCESSION_NUMBER"].isin(mult) & info["PUTCALL"].isna()]
    value = pd.to_numeric(info["VALUE"], errors="coerce").fillna(0).astype(float)
    info = info.assign(
        value_usd=value * info["ACCESSION_NUMBER"].map(mult),
        shares=pd.to_numeric(info["SSHPRNAMT"], errors="coerce"),
        cusip=info["CUSIP"].str.strip().str.upper(),
    )
    raw_total = float(info["value_usd"].sum())
    kept, stats = reconcile_units(info, ref_price, ref_shares)
    out = (
        kept.groupby("cusip", as_index=False)
        .agg(
            issuer=("NAMEOFISSUER", lambda x: x.mode().iat[0]),
            title_of_class=("TITLEOFCLASS", "first"),
            value_usd=("value_usd", "sum"),
            names=("NAMEOFISSUER", lambda x: "|".join(x.str.strip().value_counts().index[:6])),
        )
        .sort_values("value_usd", ascending=False)
        .reset_index(drop=True)
    )
    summary = {
        "year": year,
        "dataset": dataset_for_year_end(year),
        "filers": int(len(subs)),
        "positions": int(len(out)),
        "total_value_usd": float(out["value_usd"].sum()),
        "raw_value_usd": raw_total,
        **stats,
    }
    return out, summary


def reconcile_units(
    info: pd.DataFrame, ref_price: pd.Series, ref_shares: pd.Series
) -> tuple[pd.DataFrame, dict]:
    """Fix 1,000x unit slips against a reference price; drop what can't be checked."""
    is_share = info["SSHPRNAMTTYPE"].eq("SH") & (info["shares"] > 0)
    ref = info["cusip"].map(ref_price)
    usable = is_share & ref.notna() & (ref > 0)
    df = info[usable].copy()
    ref = ref[usable]
    best_value = df["value_usd"].copy()
    best_gap = (np.log10((df["value_usd"] / df["shares"]).clip(lower=1e-12) / ref)).abs()
    for factor in (1 / 1000, 1000):
        candidate = df["value_usd"] * factor
        gap = (np.log10((candidate / df["shares"]).clip(lower=1e-12) / ref)).abs()
        better = gap < best_gap
        best_value[better] = candidate[better]
        best_gap[better] = gap[better]
    changed = best_value != df["value_usd"]
    df["value_usd"] = best_value
    fits = best_gap <= np.log10(PRICE_TOLERANCE)
    plausible = df["shares"] <= df["cusip"].map(ref_shares) * MAX_SHARES_VS_BIG_THREE
    kept = df[fits & plausible]
    stats = {
        "rows_rescaled": int((changed & fits & plausible).sum()),
        "value_dropped_too_many_shares_usd": float(df.loc[fits & ~plausible, "value_usd"].sum()),
        "value_kept_usd": float(kept["value_usd"].sum()),
        "rows_dropped_off_price": int((~fits).sum()),
        "rows_dropped_too_many_shares": int((fits & ~plausible).sum()),
        "rows_dropped_not_checkable": int((~usable).sum()),
    }
    return kept, stats
