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
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wallstreet import (  # noqa: E402
    aum,
    fred,
    holdings,
    market13f,
    sec_facts,
    sectors,
    segments,
    thirteenf,
)
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

STEPS = ("fundamentals", "fred", "aum", "segments", "holdings", "sectors", "drivers")
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


UNIVERSE_TOP_FIRM = 1000  # map every CUSIP that ranks this high for any firm-quarter
UNIVERSE_TOP_MARKET = 1500  # or this high in the market at any year-end
STAKES_TOP = 500
FRAMES_URL = (
    "https://data.sec.gov/api/xbrl/frames/dei/EntityCommonStockSharesOutstanding/shares/{p}.json"
)


def shares_outstanding(fx: Fetcher, year: int) -> pd.Series:
    """Shares outstanding by CIK near a year-end, from the SEC frames API.

    10-K cover pages report shares a few weeks after the year-end, so we take
    the Q4 frame and fill gaps from the next Q1 frame.
    """
    out: dict[int, float] = {}
    for period in (f"CY{year + 1}Q1I", f"CY{year}Q4I"):
        for row in fx.get_json(FRAMES_URL.format(p=period))["data"]:
            out[int(row["cik"])] = float(row["val"])
    return pd.Series(out)


# Berkshire's class A share is worth 1,500 class B shares, so raw share counts
# can't be added up; its stake is left out.
STAKES_EXCLUDE_CIK = {1067983}


def multi_class_shares(fx: Fetcher, cik: int, year: int) -> float | None:
    """Total shares for companies the frames API leaves out.

    Companies with several share classes (Alphabet, Meta) report cover-page
    share counts per class, which the frames API skips. Their balance sheet
    gives one total: we use year-end shares outstanding, or failing that the
    average shares behind earnings per share for that year.
    """
    try:
        facts = fx.get_json(sec_facts.FACTS_URL.format(cik=cik))
    except Exception:  # noqa: BLE001
        return None
    gaap = facts.get("facts", {}).get("us-gaap", {})
    end = f"{year}-12-31"
    for tag, needs_full_year in (
        ("CommonStockSharesOutstanding", False),
        ("WeightedAverageNumberOfSharesOutstandingBasic", True),
    ):
        rows = gaap.get(tag, {}).get("units", {}).get("shares", [])
        rows = [
            r
            for r in rows
            if r["end"] == end
            and r.get("form") == "10-K"
            and (not needs_full_year or r.get("start") == f"{year}-01-01")
        ]
        if rows:
            return float(max(rows, key=lambda r: r["filed"])["val"])
    return None


def step_sectors(fx: Fetcher, settings) -> list[dict]:
    log("sectors: reading full Big Three holdings from the cache")
    full = holdings.full_holdings(fx, settings)
    year_ends = [f"{y}-12-31" for y in range(settings.start.year, settings.end.year + 1)]

    log("sectors: building the market (all 13F filers) for each year-end")
    market, summaries = {}, []
    for q in year_ends:
        year = int(q[:4])
        df, summary = market13f.market_holdings(
            fx, year, holdings.reference_prices(full, q), holdings.largest_position(full, q)
        )
        market[q] = df
        summaries.append(summary)

    log("sectors: mapping holdings to sectors")
    full["rank"] = full.groupby(["firm", "quarter_end"])["value_usd"].rank(ascending=False)
    top_market = pd.concat([df.head(UNIVERSE_TOP_MARKET) for df in market.values()])
    spellings = top_market.assign(issuer=top_market["names"].str.split("|")).explode("issuer")
    universe = (
        pd.concat(
            [
                full.loc[full["rank"] <= UNIVERSE_TOP_FIRM, ["cusip", "issuer", "title_of_class"]],
                top_market[["cusip", "issuer", "title_of_class"]],
                spellings[["cusip", "issuer", "title_of_class"]],
            ]
        )
        .dropna()
        .drop_duplicates()
    )
    mapping = sectors.map_cusips(fx, universe)
    sector_of = dict(zip(mapping["cusip"], mapping["sector"], strict=True))

    def by_sector(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
        df = df.assign(sector=df["cusip"].map(sector_of).fillna(sectors.UNMAPPED))
        out = df.groupby(keys + ["sector"], as_index=False)["value_usd"].sum()
        out["share"] = out["value_usd"] / out.groupby(keys)["value_usd"].transform("sum")
        return out

    firm_sectors = by_sector(full, ["firm", "quarter_end"])
    market_all = pd.concat([df.assign(quarter_end=q) for q, df in market.items()])
    market_sectors = by_sector(market_all, ["quarter_end"])

    log("sectors: energy holdings")
    clean_firm = full.assign(company=full["issuer"].map(sectors.clean_energy_name))
    clean_market = market_all.assign(company=market_all["issuer"].map(sectors.clean_energy_name))
    energy = []
    for _who, df, keys in (
        ("firm", firm_sectors, ["firm", "quarter_end"]),
        ("market", market_sectors.assign(firm="market"), ["firm", "quarter_end"]),
    ):
        oil = df[df["sector"] == "Energy"][keys + ["value_usd", "share"]].assign(
            group="oil_gas_coal"
        )
        energy.append(oil)
    for df in (clean_firm, clean_market.assign(firm="market")):
        total = df.groupby(["firm", "quarter_end"])["value_usd"].sum()
        clean = df[df["company"].notna()].groupby(["firm", "quarter_end"])["value_usd"].sum()
        clean = clean.reindex(total.index, fill_value=0)
        energy.append(
            pd.DataFrame(
                {"value_usd": clean, "share": clean / total, "group": "clean_energy"}
            ).reset_index()
        )
    energy_df = pd.concat(energy, ignore_index=True)
    clean_names = (
        pd.concat([clean_firm, clean_market])
        .dropna(subset=["company"])
        .groupby(["company", "issuer"], as_index=False)["value_usd"]
        .sum()
    )

    log("sectors: Big Three stakes in the largest companies")
    stakes = []
    cik_of = mapping.dropna(subset=["cik"]).set_index("cusip")["cik"].astype(int)
    for q in year_ends:
        year = int(q[:4])
        outstanding = shares_outstanding(fx, year)
        snap = full[full["quarter_end"] == q]
        combined = snap.groupby("cusip").agg(
            issuer=("issuer", "first"), value_usd=("value_usd", "sum"), shares=("shares", "sum")
        )
        for firm in holdings.FUND_MANAGERS:
            combined[f"shares_{firm}"] = (
                snap[snap["firm"] == firm].set_index("cusip")["shares"].reindex(combined.index)
            )
        combined["sector"] = combined.index.map(sector_of).fillna(sectors.UNMAPPED)
        combined = combined[combined["sector"] != sectors.FUNDS]
        combined = combined.sort_values("value_usd", ascending=False).head(STAKES_TOP)
        combined["cik"] = combined.index.map(cik_of)
        # Companies with several share classes (one CIK, several CUSIPs) add up.
        by_cik = combined.groupby("cik")["shares"].transform("sum")
        combined["shares_outstanding"] = combined["cik"].map(outstanding)
        missing = combined["shares_outstanding"].isna() & combined["cik"].notna()
        for cik in combined.loc[missing, "cik"].unique()[:40]:
            if int(cik) in STAKES_EXCLUDE_CIK:
                continue
            total = multi_class_shares(fx, int(cik), year)
            if total:
                combined.loc[combined["cik"] == cik, "shares_outstanding"] = total
        combined["stake"] = by_cik / combined["shares_outstanding"]
        combined = combined.reset_index().assign(quarter_end=q)
        stakes.append(combined)
    stakes_df = pd.concat(stakes, ignore_index=True)
    # A stake above 60% means mismatched share counts (e.g. one class only); drop it.
    stakes_df.loc[stakes_df["stake"] > 0.6, "stake"] = float("nan")

    return [
        write(mapping.sort_values("cusip"), "sector_map.csv"),
        write(firm_sectors, "holdings_by_sector.csv"),
        write(market_sectors, "market_by_sector.csv"),
        write(pd.DataFrame(summaries), "market_summary.csv"),
        write(energy_df, "energy_holdings.csv"),
        write(clean_names.sort_values("value_usd", ascending=False), "clean_energy_matches.csv"),
        write(stakes_df, "big_three_stakes.csv"),
    ]


DRIVER_SERIES = {"BOGZ1LM883164115Q": "market", "DFF": "fed_funds", "VIXCLS": "vix"}
DRIVER_START = date(1990, 1, 1)


def step_drivers(fx: Fetcher, settings) -> list[dict]:
    """Long quarterly history of the forecast drivers, 1990 to the end of the period.

    Market value: the Fed's total value of US public company shares (quarter end).
    Fed funds rate and VIX: quarterly averages of daily values.
    """
    key = fred_api_key()
    cols = {}
    for series_id, name in DRIVER_SERIES.items():
        log(f"drivers: {series_id}")
        daily = fred.fetch_series(fx, series_id, key, DRIVER_START)
        q = fred.to_quarterly(daily).set_index("quarter")
        cols[name] = q["last"] if name == "market" else q["mean"]
    df = pd.DataFrame(cols)
    df = df[(df.index >= "1990Q1") & (df.index <= f"{settings.end.year}Q4")]
    df["market_value_usd"] = df.pop("market") * 1e6
    df.index.name = "quarter"
    return [write(df.reset_index(), "drivers_quarterly.csv")]


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
        "sectors": step_sectors,
        "drivers": step_drivers,
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
