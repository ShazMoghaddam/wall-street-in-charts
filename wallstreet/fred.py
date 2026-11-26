"""Interest rates and market levels from FRED (Federal Reserve Bank of St. Louis)."""

from __future__ import annotations

from datetime import date
from urllib.parse import urlencode

import pandas as pd

from .http import Fetcher

OBS_URL = "https://api.stlouisfed.org/fred/series/observations?"


def series_url(series_id: str, api_key: str, start: date) -> str:
    query = {
        "series_id": series_id,
        "file_type": "json",
        "observation_start": start.isoformat(),
        "api_key": api_key,
    }
    return OBS_URL + urlencode(query)


def parse_observations(series_id: str, payload: dict) -> pd.DataFrame:
    """FRED marks missing values with '.', which we drop."""
    rows = [
        {"series": series_id, "date": o["date"], "value": float(o["value"])}
        for o in payload.get("observations", [])
        if o["value"] not in (".", "")
    ]
    return pd.DataFrame(rows, columns=["series", "date", "value"])


def fetch_series(
    fetcher: Fetcher, series_id: str, api_key: str, start: date, refresh: bool = False
) -> pd.DataFrame:
    return parse_observations(
        series_id, fetcher.get_json(series_url(series_id, api_key, start), refresh=refresh)
    )


def to_quarterly(daily: pd.DataFrame) -> pd.DataFrame:
    """Quarter average and quarter-end value for each series."""
    df = daily.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["quarter"] = df["date"].dt.to_period("Q").astype(str)
    df = df.sort_values("date")
    out = df.groupby(["series", "quarter"]).agg(
        mean=("value", "mean"), last=("value", "last"), observations=("value", "size")
    )
    return out.reset_index()
