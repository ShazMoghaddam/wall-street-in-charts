"""Fetch and tidy every dataset behind Wall Street in Charts.

Usage (from the repo root):

    python data/fetch.py                 # everything
    python data/fetch.py --only fred aum # some steps
    python data/fetch.py --refresh       # re-download filing lists, facts and FRED

Needs SEC_CONTACT_EMAIL and FRED_API_KEY in the environment or a local .env.
Raw downloads are cached in data/raw/ (git-ignored). Tidy CSVs are written to
data/processed/ and described in data/README.md.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wallstreet import aum, fred, sec_facts, segments, thirteenf  # noqa: E402
from wallstreet.config import (  # noqa: E402
    MANUAL,
    PROCESSED,
    RAW,
    fred_api_key,
    load_settings,
    sec_user_agent,
)
from wallstreet.edgar import list_filings  # noqa: E402
from wallstreet.http import Fetcher  # noqa: E402

STEPS = ("fundamentals", "fred", "aum", "segments", "holdings")
TOP_N = 500
REFRESHABLE = ("data.sec.gov", "api.stlouisfed.org")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def tidy_numbers(df: pd.DataFrame) -> pd.DataFrame:
    """Whole-dollar columns as integers, shares and weights to 6 decimals."""
    df = df.copy()
    for col in df.columns:
        if not pd.api.types.is_float_dtype(df[col]):
            continue
        values = df[col].dropna()
        if (col.endswith("_usd") or col == "shares") and (values == values.round()).all():
            df[col] = df[col].round().astype("Int64")
        elif col in {"weight"} or col.endswith("_share"):
            df[col] = df[col].round(6)
    return df


def write(df: pd.DataFrame, name: str) -> dict:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    path = PROCESSED / name
    df = tidy_numbers(df)
    df.to_csv(path, index=False)
    log(f"wrote {path.relative_to(PROCESSED.parent.parent)} ({len(df):,} rows)")
    return {"file": name, "rows": int(len(df))}


def in_period(quarter: pd.Series, settings) -> pd.Series:
    first = f"{settings.start.year}Q1"
    last = f"{settings.end.year}Q4"
    return (quarter >= first) & (quarter <= last)


def step_fundamentals(fx: Fetcher, settings) -> list[dict]:
    frames = []
    for firm in settings.firms.values():
        if not firm.files_results:
            continue
        log(f"fundamentals: {firm.name}")
        docs = sec_facts.fetch_company_facts(fx, firm)
        frames.append(sec_facts.firm_fundamentals(docs, firm))
    df = pd.concat(frames, ignore_index=True)
    df = df[in_period(df["quarter"], settings)]
    df = df.rename(columns={"value": "value_usd"})
    return [write(df, "fundamentals_quarterly.csv")]


def step_fred(fx: Fetcher, settings) -> list[dict]:
    key = fred_api_key()
    daily = []
    for series_id in settings.fred_series:
        log(f"fred: {series_id}")
        daily.append(fred.fetch_series(fx, series_id, key, settings.start))
    daily_df = pd.concat(daily, ignore_index=True)
    daily_df = daily_df[daily_df["date"] <= settings.end.isoformat()]
    quarterly = fred.to_quarterly(daily_df)
    return [write(daily_df, "fred_daily.csv"), write(quarterly, "fred_quarterly.csv")]


def step_aum(fx: Fetcher, settings) -> list[dict]:
    frames = []
    for key in aum.RULES:
        firm = settings.firms[key]
        log(f"aum: {firm.name}")
        frames.append(aum.firm_aum(fx, key, firm.cik, settings.start, settings.end))
    sec_rows = pd.concat(frames, ignore_index=True).rename(
        columns={"quarter_end": "as_of", "document": "reference_document"}
    )
    sec_rows["reference"] = sec_rows["accn"]
    vanguard = pd.read_csv(MANUAL / "vanguard_aum.csv")
    vanguard = vanguard.assign(firm="vanguard", reference=vanguard["url"])
    vanguard = vanguard.rename(columns={"source": "source_detail"})
    vanguard["source"] = "Vanguard published figure (" + vanguard["source_type"] + ")"
    cols = ["firm", "as_of", "aum_trillion_usd", "source", "reference"]
    df = pd.concat([sec_rows[cols], vanguard[cols]], ignore_index=True)
    return [write(df.sort_values(["firm", "as_of"]), "aum.csv")]


def step_segments(fx: Fetcher, settings) -> list[dict]:
    frames = []
    for firm in settings.firms.values():
        if firm.group != "bank":
            continue
        log(f"segments: {firm.name}")
        since = settings.start.replace(year=settings.start.year + 1)
        for filing in list_filings(fx, firm.cik[-1], {"10-K"}, since=since):
            if filing.report_date and filing.report_date > settings.end:
                continue
            xml = fx.get_bytes(segments.instance_url(fx, filing))
            frames.append(segments.parse_segments(xml, firm.key, filing))
    df = segments.latest_per_year(frames)
    df = df[(df["year"] >= settings.start.year) & (df["year"] <= settings.end.year)]
    mapping = pd.read_csv(MANUAL / "segment_map.csv")
    df = df.merge(mapping[["firm", "segment_member", "bucket"]], how="left")
    unmapped = df[df["bucket"].isna()][["firm", "segment_member"]].drop_duplicates()
    if not unmapped.empty:
        raise SystemExit(f"Unmapped segments, add them to segment_map.csv:\n{unmapped}")
    return [write(df, "bank_segments_annual.csv")]


def step_holdings(fx: Fetcher, settings) -> list[dict]:
    tops, totals = [], []
    for firm in settings.firms.values():
        if not firm.thirteenf_cik:
            continue
        filings = thirteenf.firm_quarterly_filings(fx, firm, settings.start, settings.end)
        log(f"holdings: {firm.name} ({len(filings)} quarters)")
        for quarter_end, parts in filings.items():
            rows = pd.concat(
                [
                    thirteenf.parse_info_table(
                        fx.get_bytes(thirteenf.info_table_url(fx, f)), f.filed
                    )
                    for f in parts
                ],
                ignore_index=True,
            )
            securities = thirteenf.aggregate_by_security(rows)
            top, total = thirteenf.summarise(firm.key, quarter_end, parts, securities, TOP_N)
            tops.append(top)
            totals.append(total)
    return [
        write(pd.concat(tops, ignore_index=True), f"holdings_13f_top{TOP_N}.csv"),
        write(pd.DataFrame(totals), "holdings_13f_totals.csv"),
    ]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", nargs="+", choices=STEPS, help="run only these steps")
    parser.add_argument(
        "--refresh", action="store_true", help="re-download filing lists, facts and FRED data"
    )
    args = parser.parse_args(argv)

    if args.refresh:
        for host in REFRESHABLE:
            shutil.rmtree(RAW / host, ignore_errors=True)

    settings = load_settings()
    fx = Fetcher(sec_user_agent())
    runners = {
        "fundamentals": step_fundamentals,
        "fred": step_fred,
        "aum": step_aum,
        "segments": step_segments,
        "holdings": step_holdings,
    }
    manifest_path = PROCESSED / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"steps": {}}
    for step in args.only or STEPS:
        outputs = runners[step](fx, settings)
        manifest["steps"][step] = {
            "updated": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "outputs": outputs,
        }
    manifest["period"] = {"start": settings.start.isoformat(), "end": settings.end.isoformat()}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    log("done")


if __name__ == "__main__":
    main()
