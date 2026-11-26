"""The numbers behind findings 1, 2, 7 and 8.

Every figure in the charts and the findings text comes from these functions,
so the words can never drift from the data. Each function returns a tidy
DataFrame; `headline_numbers()` collects the figures the text quotes.
"""

from __future__ import annotations

import json
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
    if (PROCESSED / "holdings_by_sector.csv").exists():
        out.update(headline_numbers_holdings())
    if (MODELS / "forecast_annual.csv").exists():
        out.update(headline_numbers_forecast())
    return out


# Findings 3 to 6: holdings and sectors ----------------------------------------

FUND_MANAGERS = ["blackrock", "vanguard", "state_street"]
SECTORS = [
    "Technology",
    "Financials",
    "Health care",
    "Industrials",
    "Consumer discretionary",
    "Communication",
    "Consumer staples",
    "Energy",
    "Real estate",
    "Utilities",
    "Materials",
]


@cache
def holdings_by_sector() -> pd.DataFrame:
    return pd.read_csv(PROCESSED / "holdings_by_sector.csv")


@cache
def market_by_sector() -> pd.DataFrame:
    return pd.read_csv(PROCESSED / "market_by_sector.csv")


def sector_weights(who: str = "big_three") -> pd.DataFrame:
    """Quarter ends as rows, the 11 sectors as columns, shares adding to 1.

    Funds (ETFs) and holdings we couldn't map are left out and the rest
    scaled to 100%, so firms and the market compare like with like.
    `who` is a firm key, "big_three" (the three combined) or "market".
    """
    if who == "market":
        df = market_by_sector()
    else:
        df = holdings_by_sector()
        df = df[df["firm"].isin(FUND_MANAGERS if who == "big_three" else [who])]
    df = df[df["sector"].isin(SECTORS)]
    wide = df.groupby(["quarter_end", "sector"])["value_usd"].sum().unstack("sector")
    wide = wide.div(wide.sum(axis=1), axis=0)
    return wide[SECTORS]


def mapped_share() -> pd.DataFrame:
    """How much of each firm's value was mapped to a sector, by quarter."""
    df = holdings_by_sector()
    total = df.groupby(["firm", "quarter_end"])["value_usd"].sum()
    mapped = df[df["sector"] != "Not mapped"].groupby(["firm", "quarter_end"])["value_usd"].sum()
    return (mapped / total).unstack("firm")


def distance_from_market() -> pd.DataFrame:
    """Half the summed gaps between a firm's sector weights and the market's.

    0% means an exact copy of the market's sector mix; 100% means no overlap.
    Year-ends as rows, firms as columns.
    """
    market = sector_weights("market")
    out = {}
    for firm in FUND_MANAGERS:
        w = sector_weights(firm).loc[market.index]
        out[firm] = (w - market).abs().sum(axis=1) / 2
    return pd.DataFrame(out)


@cache
def energy_holdings() -> pd.DataFrame:
    return pd.read_csv(PROCESSED / "energy_holdings.csv")


def energy_share(group: str) -> pd.DataFrame:
    """Share of 13F value in oil, gas and coal or in clean energy. Quarters x firms."""
    df = energy_holdings()
    df = df[df["group"] == group]
    return df.pivot(index="quarter_end", columns="firm", values="share")


def energy_value(group: str) -> pd.DataFrame:
    df = energy_holdings()
    df = df[df["group"] == group]
    return df.pivot(index="quarter_end", columns="firm", values="value_usd")


def big_three_market_share() -> pd.DataFrame:
    """Each firm's 13F company shares (funds left out) as a share of all US public shares."""
    df = holdings_by_sector()
    df = df[df["firm"].isin(FUND_MANAGERS) & (df["sector"] != "Funds (ETFs)")]
    held = df.groupby(["quarter_end", "firm"])["value_usd"].sum().unstack("firm")
    q = fred_quarterly()
    market = q[q["series"] == "BOGZ1LM883164115Q"].set_index("quarter")["last"] * 1e6
    quarters = pd.PeriodIndex(pd.to_datetime(held.index), freq="Q").astype(str)
    share = held.div(market.reindex(quarters).to_numpy(), axis=0)
    return share[FUND_MANAGERS]


@cache
def stakes() -> pd.DataFrame:
    df = pd.read_csv(PROCESSED / "big_three_stakes.csv", dtype={"cusip": str})
    # One row per company: share classes (Alphabet A and C) carry the same stake.
    return df.dropna(subset=["stake"]).drop_duplicates(["quarter_end", "cik"])


def headline_numbers_holdings() -> dict:
    out: dict = {}
    first, last = "2015-12-31", "2025-12-31"
    b3, mk = sector_weights("big_three"), sector_weights("market")
    out["tech_share_2015"] = b3.loc[first, "Technology"]
    out["tech_share_2025"] = b3.loc[last, "Technology"]
    out["market_tech_share_2025"] = mk.loc[last, "Technology"]
    out["energy_share_2015"] = b3.loc[first, "Energy"]
    out["energy_share_2025"] = b3.loc[last, "Energy"]
    change = (b3.loc[last] - b3.loc[first]).sort_values()
    fallers = [x.lower() for x in change.index[:4]]
    out["biggest_fallers"] = ", ".join(fallers[:-1]) + " and " + fallers[-1]
    out["sectors_grew"] = int((change > 0).sum())
    top = b3.loc[last].sort_values(ascending=False)
    out["top_sector_2025"] = top.index[0]
    out["top_sector_2025_share"] = top.iloc[0]
    d = distance_from_market()
    for firm in FUND_MANAGERS:
        out[f"{firm}_distance_2015"] = d.loc[first, firm]
        out[f"{firm}_distance_2025"] = d.loc[last, firm]
    out["max_distance_2025"] = d.loc[last].max()
    out["vanguard_real_estate_2015"] = sector_weights("vanguard").loc[first, "Real estate"]
    out["market_real_estate_2015"] = mk.loc[first, "Real estate"]
    oil = energy_share("oil_gas_coal")
    clean = energy_share("clean_energy")
    for firm in FUND_MANAGERS + ["market"]:
        out[f"{firm}_oil_2015"] = oil.loc[first, firm]
        out[f"{firm}_oil_2025"] = oil.loc[last, firm]
    clean_b3 = energy_value("clean_energy")[FUND_MANAGERS].sum(axis=1)
    out["clean_peak_quarter"] = clean_b3.idxmax()
    out["clean_value_peak_bn"] = clean_b3.max() / 1e9
    out["clean_value_2025_bn"] = clean_b3.loc[last] / 1e9
    out["oil_value_2025_bn"] = energy_value("oil_gas_coal").loc[last, FUND_MANAGERS].sum() / 1e9
    out["clean_share_peak"] = clean[FUND_MANAGERS].mean(axis=1).max()
    share = big_three_market_share()
    total = share.sum(axis=1)
    out["big_three_share_2015"] = total.loc[first]
    out["big_three_share_2025"] = total.loc[last]
    for firm in FUND_MANAGERS:
        out[f"{firm}_market_share_2025"] = share.loc[last, firm]
    s = stakes()
    for q, label in ((first, "2015"), (last, "2025")):
        snap = s[s["quarter_end"] == q]
        out[f"median_stake_{label}"] = snap["stake"].median()
        out[f"stakes_over_20pct_{label}"] = int((snap["stake"] > 0.20).sum())
        out[f"stakes_companies_{label}"] = int(len(snap))
    snap = s[s["quarter_end"] == last].head(5)
    for i, row in enumerate(snap.itertuples(), start=1):
        out[f"top{i}_company"] = row.issuer
        out[f"top{i}_stake"] = row.stake
    cov = mapped_share()
    out["mapped_share_min"] = cov[FUND_MANAGERS].min().min()
    return out


# Finding 9: scenarios ---------------------------------------------------------

MODELS = PROCESSED.parent.parent / "models"
SCENARIOS = ["bad", "middling", "good"]


@cache
def forecast_table() -> pd.DataFrame:
    return pd.read_csv(MODELS / "forecast_annual.csv")


@cache
def backtest_table() -> pd.DataFrame:
    return pd.read_csv(MODELS / "backtest_annual.csv")


@cache
def driver_scenarios() -> pd.DataFrame:
    return pd.read_csv(MODELS / "drivers_annual.csv").set_index("year")


def scenario_paths(firm: str, metric: str) -> pd.DataFrame:
    """Years as rows, bad / middling / good as columns ($bn).

    History (to 2025) is copied into all three so the lines share it and then
    split; this is how the charts show 'history, then three futures'.
    """
    df = forecast_table()
    df = df[(df["firm"] == firm) & (df["metric"] == metric)].set_index("year")
    hist = df["actual"].dropna()
    future = df[SCENARIOS].dropna()
    out = pd.DataFrame({s: pd.concat([hist, future[s]]) for s in SCENARIOS})
    return out


def backtest_summary() -> pd.DataFrame:
    """Average absolute error (%) and share of years inside the range, per firm and metric."""
    b = backtest_table()
    return b.groupby(["firm", "metric"]).agg(
        error=("error_pct", lambda x: x.abs().mean()),
        inside=("inside_range", "mean"),
        actual_total=("actual", "sum"),
        predicted_total=("predicted_with_real_drivers", "sum"),
    )


def headline_numbers_forecast() -> dict:
    out: dict = {}
    for firm in LISTED:
        for metric in ("revenue", "net_income"):
            p = scenario_paths(firm, metric)
            for year in (2030, 2035):
                for s in SCENARIOS:
                    out[f"{firm}_{metric}_{year}_{s}_bn"] = float(p.loc[year, s])
            out[f"{firm}_{metric}_2025_bn"] = float(p.loc[2025, "middling"])
    for firm in ("blackrock", "state_street"):
        p = scenario_paths(firm, "aum")
        out[f"{firm}_aum_2025_tn"] = float(p.loc[2025, "middling"]) / 1000
        for s in SCENARIOS:
            out[f"{firm}_aum_2035_{s}_tn"] = float(p.loc[2035, s]) / 1000
    d = driver_scenarios()
    for s in SCENARIOS:
        out[f"market_2035_{s}"] = float(d.loc[2035, f"market_{s}"])
        out[f"rate_2035_{s}"] = float(d.loc[2035, f"rate_{s}"])
    b = backtest_table()
    s = backtest_summary()
    out["backtest_inside_share"] = float(b["inside_range"].mean())
    out["backtest_revenue_error_min"] = float(s.xs("revenue", level="metric")["error"].min())
    out["backtest_revenue_error_max"] = float(s.xs("revenue", level="metric")["error"].max())
    for firm in LISTED:
        out[f"{firm}_backtest_profit_error"] = float(s.loc[(firm, "net_income"), "error"])
    err = s.xs("net_income", level="metric")["error"]
    out["backtest_profit_best"] = err.idxmin()
    out["backtest_profit_worst"] = err.idxmax()
    settings = json.loads((MODELS / "settings.json").read_text())
    out["rate_long_run_mean"] = float(settings["rate_long_run_mean"])
    out["market_growth_per_year_history"] = float(settings["market_growth_per_year_history"])
    width = {
        firm: (out[f"{firm}_net_income_2035_good_bn"] - out[f"{firm}_net_income_2035_bad_bn"])
        / out[f"{firm}_net_income_2035_middling_bn"]
        for firm in LISTED
    }
    out["widest_ranges"] = sorted(width, key=width.get, reverse=True)[:2]
    profit_2035 = {firm: out[f"{firm}_net_income_2035_middling_bn"] for firm in LISTED}
    out["profit_2035_bad_below_2025"] = [
        firm
        for firm in LISTED
        if out[f"{firm}_net_income_2035_bad_bn"] < out[f"{firm}_net_income_2025_bn"]
    ]
    out["profit_2035_leader"] = max(profit_2035, key=profit_2035.get)
    return out
