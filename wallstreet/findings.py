"""The numbers behind findings 1, 2, 7 and 8.

Every figure in the charts and the findings text comes from these functions,
so the words can never drift from the data. Each function returns a tidy
DataFrame; `headline_numbers()` collects the figures the text quotes.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

import pandas as pd

from .config import PROCESSED, load_settings

FIRM_ORDER = ["jpmorgan", "goldman", "morgan_stanley", "blackrock", "vanguard", "state_street"]
BANKS = ["jpmorgan", "goldman", "morgan_stanley"]
LISTED = ["jpmorgan", "goldman", "morgan_stanley", "blackrock", "state_street"]
BUCKETS = {
    "markets_dealmaking": "Trading and dealmaking",
    "wealth_asset_management": "Wealth and asset management",
    "banking_lending": "Banking and lending",
}


# Short names for charts, where space is tight.
BUCKET_SHORT = {
    "markets_dealmaking": "Markets",
    "wealth_asset_management": "Wealth",
    "banking_lending": "Lending",
}
STRESS_LEVEL = 30  # VIX above this counts as a day of market stress


@dataclass(frozen=True)
class Shock:
    key: str
    name: str
    during: tuple[str, str]  # quarters, inclusive
    before: tuple[str, str]  # the same quarters a year earlier


SHOCKS = [
    Shock("covid", "2020 pandemic", ("2020Q1", "2020Q2"), ("2019Q1", "2019Q2")),
    Shock("rates", "2022 rate rises", ("2022Q1", "2022Q4"), ("2021Q1", "2021Q4")),
    Shock("banks", "2023 bank failures", ("2023Q1", "2023Q2"), ("2022Q1", "2022Q2")),
]


def short_name(firm: str) -> str:
    return load_settings().firms[firm].short


@cache
def fundamentals() -> pd.DataFrame:
    df = pd.read_csv(PROCESSED / "fundamentals_quarterly.csv")
    df["year"] = df["quarter"].str[:4].astype(int)
    return df


@cache
def fred_quarterly() -> pd.DataFrame:
    return pd.read_csv(PROCESSED / "fred_quarterly.csv")


def quarterly(metric: str, firms: list[str] = LISTED) -> pd.DataFrame:
    """Quarters as rows, firms as columns, US dollars."""
    df = fundamentals()
    wide = df[df["metric"] == metric].pivot(index="quarter", columns="firm", values="value_usd")
    return wide[[f for f in firms if f in wide.columns]]


def yearly(metric: str, firms: list[str] = LISTED) -> pd.DataFrame:
    """Calendar-year totals (flows) or year-end values (total assets)."""
    df = fundamentals()
    df = df[df["metric"] == metric]
    if metric == "total_assets":
        df = df[df["quarter"].str.endswith("Q4")]
        wide = df.pivot(index="year", columns="firm", values="value_usd")
    else:
        wide = df.groupby(["year", "firm"])["value_usd"].sum().unstack("firm")
    return wide[[f for f in firms if f in wide.columns]]


# Finding 1: who grew biggest -------------------------------------------------


def growth_table() -> pd.DataFrame:
    """Revenue and profit in the first and last year, and how many times bigger."""
    settings = load_settings()
    first, last = settings.start.year, settings.end.year
    rows = []
    for firm in LISTED:
        rev, ni = yearly("revenue")[firm], yearly("net_income")[firm]
        rows.append(
            {
                "firm": firm,
                "revenue_first": rev[first],
                "revenue_last": rev[last],
                "revenue_multiple": rev[last] / rev[first],
                "profit_first": ni[first],
                "profit_last": ni[last],
                "profit_multiple": ni[last] / ni[first],
                "profit_cagr": (ni[last] / ni[first]) ** (1 / (last - first)) - 1,
                "margin_last": ni[last] / rev[last],
            }
        )
    return pd.DataFrame(rows).set_index("firm")


@cache
def aum() -> pd.DataFrame:
    df = pd.read_csv(PROCESSED / "aum.csv")
    df["as_of"] = pd.to_datetime(df["as_of"])
    return df


def aum_quarterly() -> pd.DataFrame:
    """BlackRock and State Street AUM at each quarter end, $ trillions."""
    df = aum()
    df = df[df["firm"].isin(["blackrock", "state_street"])]
    return df.pivot(index="as_of", columns="firm", values="aum_trillion_usd")


def vanguard_aum() -> pd.Series:
    df = aum()
    return df[df["firm"] == "vanguard"].set_index("as_of")["aum_trillion_usd"]


# Finding 2: where the banks make money --------------------------------------


@cache
def segments() -> pd.DataFrame:
    df = pd.read_csv(PROCESSED / "bank_segments_annual.csv")
    return df[(df["metric"] == "revenue") & df["bucket"].isin(BUCKETS)]


def segment_mix(firm: str) -> pd.DataFrame:
    """Years as rows, buckets as columns, US dollars."""
    df = segments()
    df = df[df["firm"] == firm]
    wide = df.groupby(["year", "bucket"])["value_usd"].sum().unstack("bucket").fillna(0)
    return wide[[b for b in BUCKETS if b in wide.columns]]


def segment_share(firm: str, year: int) -> pd.Series:
    mix = segment_mix(firm).loc[year]
    return mix / mix.sum()


# Finding 7: rates rose in 2022 ----------------------------------------------


def fed_funds_quarterly() -> pd.Series:
    q = fred_quarterly()
    return q[q["series"] == "DFF"].set_index("quarter")["mean"]


def rate_rise_change(start: int = 2021, end: int = 2023) -> pd.DataFrame:
    """Profit and net interest income in the year before and after the rate rises."""
    ni, nii = yearly("net_income"), yearly("net_interest_income", BANKS + ["state_street"])
    rows = []
    for firm in LISTED:
        row = {
            "firm": firm,
            "profit_start": ni.loc[start, firm],
            "profit_end": ni.loc[end, firm],
        }
        row["profit_change"] = row["profit_end"] - row["profit_start"]
        row["profit_change_pct"] = row["profit_end"] / row["profit_start"] - 1
        if firm in nii.columns:
            row["nii_start"] = nii.loc[start, firm]
            row["nii_end"] = nii.loc[end, firm]
            row["nii_change_pct"] = row["nii_end"] / row["nii_start"] - 1
        rows.append(row)
    return pd.DataFrame(rows).set_index("firm")


def nii_vs_rates(base_year: int = 2019) -> pd.DataFrame:
    """Quarterly net interest income, indexed to the base year's average (= 100)."""
    nii = quarterly("net_interest_income", BANKS + ["state_street"])
    base = nii[nii.index.str.startswith(str(base_year))].mean()
    index = nii / base * 100
    rate = fed_funds_quarterly()
    long = index.reset_index().melt(id_vars="quarter", var_name="firm", value_name="nii_index")
    long["fed_funds"] = long["quarter"].map(rate)
    return long.dropna()


# Finding 8: shocks ----------------------------------------------------------


def shock_changes() -> pd.DataFrame:
    """Profit in each shock window against the same quarters a year earlier."""
    ni = quarterly("net_income")
    rows = []
    for shock in SHOCKS:
        during = ni.loc[shock.during[0] : shock.during[1]].sum()
        before = ni.loc[shock.before[0] : shock.before[1]].sum()
        for firm in LISTED:
            rows.append(
                {
                    "shock": shock.key,
                    "shock_name": shock.name,
                    "firm": firm,
                    "profit_before": before[firm],
                    "profit_during": during[firm],
                    "change_pct": during[firm] / before[firm] - 1,
                }
            )
    return pd.DataFrame(rows)


def profit_growth_yoy() -> pd.DataFrame:
    """Each quarter's profit against the same quarter a year earlier, long format."""
    ni = quarterly("net_income")
    yoy = ni / ni.shift(4) - 1
    long = yoy.dropna().reset_index().melt(id_vars="quarter", var_name="firm", value_name="yoy")
    return long


def vix_daily(year: int) -> pd.Series:
    df = pd.read_csv(PROCESSED / "fred_daily.csv")
    df = df[(df["series"] == "VIXCLS") & df["date"].str.startswith(str(year))]
    s = df.set_index(pd.to_datetime(df["date"]))["value"]
    return s


def stress_days(year: int) -> pd.Series:
    """1 on trading days when the VIX closed above STRESS_LEVEL, else 0."""
    return (vix_daily(year) > STRESS_LEVEL).astype(int)


# Headline numbers -----------------------------------------------------------


def headline_numbers() -> dict:
    """Every number the findings text quotes, rounded the way the text uses it."""
    g = growth_table()
    r = rate_rise_change()
    s = shock_changes()
    rate = fed_funds_quarterly()
    out: dict = {}
    for firm in LISTED:
        out[f"{firm}_revenue_2015_bn"] = g.loc[firm, "revenue_first"] / 1e9
        out[f"{firm}_revenue_2025_bn"] = g.loc[firm, "revenue_last"] / 1e9
        out[f"{firm}_profit_2015_bn"] = g.loc[firm, "profit_first"] / 1e9
        out[f"{firm}_profit_2025_bn"] = g.loc[firm, "profit_last"] / 1e9
        out[f"{firm}_profit_multiple"] = g.loc[firm, "profit_multiple"]
        out[f"{firm}_revenue_multiple"] = g.loc[firm, "revenue_multiple"]
        out[f"{firm}_profit_change_2021_2023_pct"] = r.loc[firm, "profit_change_pct"]
    for firm in BANKS + ["state_street"]:
        out[f"{firm}_nii_change_2021_2023_pct"] = r.loc[firm, "nii_change_pct"]
        out[f"{firm}_nii_2023_bn"] = r.loc[firm, "nii_end"] / 1e9
        out[f"{firm}_nii_2021_bn"] = r.loc[firm, "nii_start"] / 1e9
    for row in s.itertuples():
        out[f"{row.firm}_{row.shock}_change_pct"] = row.change_pct
    out["fed_funds_2021_avg"] = rate.loc["2021Q1":"2021Q4"].mean()
    out["fed_funds_2023_avg"] = rate.loc["2023Q1":"2023Q4"].mean()
    out["blackrock_aum_2015q4"] = aum_quarterly().loc["2015-12-31", "blackrock"]
    out["blackrock_aum_2025q4"] = aum_quarterly().loc["2025-12-31", "blackrock"]
    out["state_street_aum_2015q4"] = aum_quarterly().loc["2015-12-31", "state_street"]
    out["state_street_aum_2025q4"] = aum_quarterly().loc["2025-12-31", "state_street"]
    out["vanguard_aum_2025"] = vanguard_aum().iloc[-1]
    for firm in BANKS:
        share = segment_share(firm, load_settings().end.year)
        for bucket, value in share.items():
            out[f"{firm}_{bucket}_share_2025"] = value
    out["biggest_profit_grower"] = g["profit_multiple"].idxmax()
    out["vix_2020_peak"] = vix_daily(2020).max()
    out["vix_2020_peak_date"] = vix_daily(2020).idxmax().strftime("%-d %B %Y")
    margins = quarterly("net_income") / quarterly("revenue")
    spread = margins.quantile(0.75) - margins.quantile(0.25)
    out["widest_margin_spread"] = spread.idxmax()
    for year in (2020, 2022, 2023):
        out[f"stress_days_{year}"] = int(stress_days(year).sum())
    return out
