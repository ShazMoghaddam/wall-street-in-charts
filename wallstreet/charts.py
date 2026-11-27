"""Bezel Charts for findings 1, 2, 7 and 8, in light and dark themes.

Each firm keeps the same colour in every chart, so a reader learns the key
once. Each builder returns {name: Chart}; build_all() renders both themes.
"""

from __future__ import annotations

from collections.abc import Callable

import bezel_charts as bc
import pandas as pd

from . import findings as F

THEMES = ("light", "dark")
WIDE = 760
HALF = 372

# Palette index per firm, so colours stay the same across charts and themes.
FIRM_COLOUR = {
    "jpmorgan": 0,
    "blackrock": 1,
    "vanguard": 2,
    "goldman": 3,
    "morgan_stanley": 4,
    "state_street": 5,
}
BUCKET_COLOUR = {"markets_dealmaking": 1, "wealth_asset_management": 2, "banking_lending": 3}


def palette(theme: str) -> list[str]:
    return bc.themes[theme]["palette"]


def firm_colours(firms: list[str], theme: str) -> list[str]:
    p = palette(theme)
    return [p[FIRM_COLOUR[f]] for f in firms]


def names(firms) -> list[str]:
    return [F.short_name(f) for f in firms]


def bn(series_or_frame):
    return (series_or_frame / 1e9).round(1)


# Finding 1 ------------------------------------------------------------------


def revenue_line(theme: str) -> bc.Chart:
    df = bn(F.yearly("revenue"))
    df.columns = names(df.columns)
    return bc.line(
        df,
        heading="Revenue by year · $bn",
        prefix="$",
        suffix="bn",
        stat="none",
        markers=True,
        color=firm_colours(list(F.LISTED), theme),
        notes={"2020": "Pandemic", "2022": "Rates rise"},
        theme=theme,
        width=WIDE,
        height=360,
    )


def profit_growth_bars(theme: str) -> bc.Chart:
    g = F.growth_table().sort_values("profit_multiple", ascending=False)
    s = g["profit_multiple"].round(2)
    s.index = names(s.index)
    return bc.bars(
        s,
        heading="Profit 2025 vs 2015 · times bigger",
        suffix="×",
        decimals=1,
        horizontal=True,
        show_values=True,
        goal=1,
        goal_label="No growth",
        color=firm_colours(list(g.index), theme),
        theme=theme,
        width=HALF,
        height=300,
    )


def aum_area(theme: str) -> bc.Chart:
    df = F.aum_quarterly()
    df.columns = names(df.columns)
    return bc.area(
        df,
        heading="Assets under management · $ trillion",
        prefix="$",
        suffix="T",
        decimals=1,
        x_format="%Y",
        color=firm_colours(["blackrock", "state_street"], theme),
        notes={"2020-03-31": "Covid sell-off"},
        theme=theme,
        width=WIDE,
        height=340,
    )


def vanguard_line(theme: str) -> bc.Chart:
    s = F.vanguard_aum()
    s.name = "Vanguard"
    return bc.line(
        s,
        heading="Vanguard AUM · published figures · $T",
        prefix="$",
        suffix="T",
        decimals=1,
        markers=["diamond"],
        straight=True,
        x_format="%b %Y",
        color=firm_colours(["vanguard"], theme),
        theme=theme,
        width=HALF,
        height=300,
    )


def bank_assets_sparks(theme: str) -> dict[str, bc.Chart]:
    assets = F.yearly("total_assets", F.BANKS) / 1e12
    out = {}
    for firm in F.BANKS:
        s = assets[firm].round(2)
        out[f"f1-assets-{firm.replace('_', '-')}"] = bc.spark(
            s,
            heading=f"{F.short_name(firm)} · total assets",
            prefix="$",
            suffix="T",
            decimals=2,
            color=firm_colours([firm], theme),
            theme=theme,
            width=300,
        )
    return out


# Finding 2 ------------------------------------------------------------------


def mix_donuts(theme: str) -> dict[str, bc.Chart]:
    year = F.load_settings().end.year
    p = palette(theme)
    out = {}
    for firm in F.BANKS:
        mix = F.segment_mix(firm).loc[year]
        mix = mix[mix > 0] / 1e9
        out[f"f2-mix-{firm.replace('_', '-')}"] = bc.donut(
            {F.BUCKET_SHORT[b]: round(v, 1) for b, v in mix.items()},
            heading=f"{F.short_name(firm)} · {year} revenue",
            prefix="$",
            suffix="bn",
            decimals=1,
            center_label="Revenue",
            color=[p[BUCKET_COLOUR[b]] for b in mix.index],
            theme=theme,
            width=300,
        )
    return out


def segment_combos(theme: str) -> dict[str, bc.Chart]:
    p = palette(theme)
    margin = F.yearly("net_income", F.BANKS) / F.yearly("revenue", F.BANKS) * 100
    out = {}
    for firm in F.BANKS:
        mix = (F.segment_mix(firm) / 1e9).round(1)
        cols = list(mix.columns)
        df = mix.rename(columns=F.BUCKET_SHORT)
        df["Profit margin"] = margin[firm].round(1)
        df.index = df.index.astype(str)
        out[f"f2-segments-{firm.replace('_', '-')}"] = bc.combo(
            df,
            bars=[F.BUCKET_SHORT[c] for c in cols],
            line="Profit margin",
            stacked=True,
            prefix="$",
            suffix="bn",
            line_suffix="%",
            line_decimals=0,
            heading=f"{F.short_name(firm)} · revenue by business and profit margin",
            color=[p[BUCKET_COLOUR[c]] for c in cols] + [palette(theme)[FIRM_COLOUR[firm]]],
            theme=theme,
            width=WIDE,
            height=340,
        )
    return out


# Finding 7 ------------------------------------------------------------------


def rates_combo(theme: str) -> bc.Chart:
    ni = F.quarterly("net_income")
    df = pd.DataFrame(
        {
            "Banks": ni[F.BANKS].sum(axis=1) / 1e9,
            "Fund managers": ni[["blackrock", "state_street"]].sum(axis=1) / 1e9,
        }
    ).round(1)
    df["Fed funds rate"] = F.fed_funds_quarterly().reindex(df.index).round(2)
    df = df.loc["2019Q1":]
    p = palette(theme)
    return bc.combo(
        df,
        bars=["Banks", "Fund managers"],
        line="Fed funds rate",
        prefix="$",
        suffix="bn",
        line_suffix="%",
        line_decimals=1,
        heading="Quarterly profit and the Fed's interest rate",
        color=[p[0], p[1], p[3]],
        theme=theme,
        width=WIDE,
        height=360,
    )


def rates_waterfall(theme: str) -> bc.Chart:
    r = F.rate_rise_change()
    steps = {"2021 profit": round(r["profit_start"].sum() / 1e9, 1)}
    for firm in r.sort_values("profit_change").index:
        steps[F.short_name(firm)] = round(r.loc[firm, "profit_change"] / 1e9, 1)
    steps["2023 profit"] = 0
    p = palette(theme)
    return bc.waterfall(
        steps,
        totals=["2021 profit", "2023 profit"],
        prefix="$",
        suffix="bn",
        decimals=1,
        heading="Who gained and lost profit, 2021 to 2023",
        color=[bc.themes[theme]["up"], bc.themes[theme]["down"], p[0]],
        theme=theme,
        width=WIDE,
        height=340,
    )


def nii_bars(theme: str) -> bc.Chart:
    r = F.rate_rise_change().dropna(subset=["nii_start"])
    df = pd.DataFrame(
        {"2021": (r["nii_start"] / 1e9).round(1), "2023": (r["nii_end"] / 1e9).round(1)}
    )
    df.index = names(df.index)
    p = palette(theme)
    return bc.bars(
        df,
        heading="Net interest income · $bn",
        prefix="$",
        suffix="bn",
        show_values=True,
        color=[p[4], p[1]],
        patterns=["solid", "stripes"],
        horizontal=True,
        theme=theme,
        width=HALF,
        height=300,
    )


def nii_scatter(theme: str) -> bc.Chart:
    df = F.nii_vs_rates()
    df = df.assign(nii_index=df["nii_index"].round(0), fed_funds=df["fed_funds"].round(2))
    df["firm"] = names(df["firm"])
    firms = ["jpmorgan", "goldman", "morgan_stanley", "state_street"]
    return bc.scatter(
        df,
        x="fed_funds",
        y="nii_index",
        by="firm",
        trend=True,
        x_label="Fed funds rate (%)",
        y_label="Net interest income (2019 = 100)",
        heading="Net interest income vs the Fed rate",
        color=firm_colours(firms, theme),
        markers=["circle", "square", "triangle", "diamond"],
        theme=theme,
        width=HALF,
        height=320,
    )


# Finding 8 ------------------------------------------------------------------


def shock_bars(theme: str) -> bc.Chart:
    s = F.shock_changes()
    df = s.pivot(index="shock_name", columns="firm", values="change_pct") * 100
    df = df.loc[[x.name for x in F.SHOCKS], F.LISTED].round(0)
    df.columns = names(df.columns)
    return bc.bars(
        df,
        heading="Profit change in each shock vs a year earlier · %",
        suffix="%",
        decimals=0,
        show_values=True,
        color=firm_colours(F.LISTED, theme),
        theme=theme,
        width=WIDE,
        height=340,
    )


def stress_heatmap(theme: str) -> bc.Chart:
    s = F.stress_days(2020)
    return bc.heatmap(
        s,
        heading=f"Days of market stress in 2020 · VIX above {F.STRESS_LEVEL}",
        stat="total",
        decimals=0,
        suffix=" days",
        theme=theme,
        width=WIDE,
    )


def margin_boxplot(theme: str) -> bc.Chart:
    ni, rev = F.quarterly("net_income"), F.quarterly("revenue")
    margin = (ni / rev * 100).round(1)
    margin.columns = names(margin.columns)
    return bc.boxplot(
        margin,
        heading="How much quarterly profit margins swing · %",
        suffix="%",
        mark="mean",
        color=firm_colours(F.LISTED, theme),
        theme=theme,
        width=WIDE,
        height=320,
    )


BUILDERS: list[Callable] = [
    revenue_line,
    profit_growth_bars,
    aum_area,
    vanguard_line,
    bank_assets_sparks,
    mix_donuts,
    segment_combos,
    rates_combo,
    rates_waterfall,
    nii_bars,
    nii_scatter,
    shock_bars,
    stress_heatmap,
    margin_boxplot,
]

NAMES = {
    revenue_line: "f1-revenue",
    profit_growth_bars: "f1-profit-growth",
    aum_area: "f1-aum",
    vanguard_line: "f1-vanguard-aum",
    rates_combo: "f7-profit-and-rates",
    rates_waterfall: "f7-profit-waterfall",
    nii_bars: "f7-net-interest-income",
    nii_scatter: "f7-nii-vs-rates",
    shock_bars: "f8-shocks",
    stress_heatmap: "f8-stress-days-2020",
    margin_boxplot: "f8-margin-spread",
}


def build_all() -> dict[str, dict[str, bc.Chart]]:
    """{name: {theme: Chart}} for every chart."""
    out: dict[str, dict[str, bc.Chart]] = {}
    for builder in BUILDERS:
        for theme in THEMES:
            result = builder(theme)
            charts = result if isinstance(result, dict) else {NAMES[builder]: result}
            for name, chart in charts.items():
                out.setdefault(name, {})[theme] = chart
    return out


# Findings 3 to 6 -------------------------------------------------------------

SECTOR_COLOURS = {
    "light": {
        "Technology": "#6E70F0",
        "Financials": "#2F8FE0",
        "Health care": "#16A884",
        "Industrials": "#D99A0E",
        "Consumer discretionary": "#E2508C",
        "Communication": "#EE6431",
        "Consumer staples": "#8E5BD0",
        "Energy": "#5C5470",
        "Real estate": "#C2417A",
        "Utilities": "#0FA3B1",
        "Materials": "#8A9A2B",
    },
    "dark": {
        "Technology": "#9FA1FF",
        "Financials": "#7CC4FF",
        "Health care": "#5EE6C8",
        "Industrials": "#FFC857",
        "Consumer discretionary": "#F675A8",
        "Communication": "#FF8A5B",
        "Consumer staples": "#B79CFF",
        "Energy": "#B8B2C8",
        "Real estate": "#FF6F91",
        "Utilities": "#4FD8E6",
        "Materials": "#C6D365",
    },
}
MARKET_COLOUR = {"light": "#8C8AA0", "dark": "#8C8AA0"}


def year_ends(df: pd.DataFrame) -> pd.DataFrame:
    df = df[df.index.str.endswith("12-31")]
    df.index = df.index.str[:4]
    return df


def sector_area(theme: str) -> bc.Chart:
    w = (year_ends(F.sector_weights("big_three")) * 100).round(1)
    return bc.area(
        w,
        stacked=True,
        max=100,
        heading="Big Three · sector mix of their US shares",
        suffix="%",
        decimals=0,
        color=[SECTOR_COLOURS[theme][s] for s in w.columns],
        theme=theme,
        width=WIDE,
        height=380,
    )


def sector_shift_bars(theme: str) -> bc.Chart:
    w = year_ends(F.sector_weights("big_three"))
    change = ((w.iloc[-1] - w.iloc[0]) * 100).round(1).sort_values(ascending=False)
    return bc.bars(
        change,
        heading="Change in sector share, 2015 to 2025 · points",
        suffix=" pts",
        decimals=1,
        show_values=True,
        angle_labels=True,
        color=[SECTOR_COLOURS[theme][s] for s in change.index],
        theme=theme,
        width=WIDE,
        height=360,
    )


def sector_bullets(theme: str) -> bc.Chart:
    last = F.sector_weights("big_three").index[-1]
    b3 = (F.sector_weights("big_three").loc[last] * 100).round(1)
    mk = (F.sector_weights("market").loc[last] * 100).round(1)
    df = pd.DataFrame({"sector": b3.index, "big_three": b3.values, "market": mk.values})
    return bc.bullet(
        df,
        x="sector",
        y="big_three",
        target="market",
        series=["Big Three", "Market"],
        zones=[5, 15],
        zone_labels=["Small", "Mid", "Large"],
        suffix="%",
        decimals=1,
        heading="Big Three vs the market, 2025 · bar = Big Three, mark = market",
        color=[palette(theme)[0]],
        theme=theme,
        width=WIDE,
        height=460,
    )


def distance_line(theme: str) -> bc.Chart:
    d = (F.distance_from_market() * 100).round(1)
    d.index = d.index.str[:4]
    d.columns = names(d.columns)
    return bc.line(
        d,
        heading="How far each sector mix is from the market · 0% = exact copy",
        suffix="%",
        decimals=1,
        zero=True,
        markers=True,
        min=0,
        max=10,
        color=firm_colours(F.FUND_MANAGERS, theme),
        theme=theme,
        width=HALF,
        height=320,
    )


def oil_line(theme: str) -> bc.Chart:
    oil = (year_ends(F.energy_share("oil_gas_coal")) * 100).round(2)
    oil = oil[F.FUND_MANAGERS + ["market"]]
    oil.columns = names(F.FUND_MANAGERS) + ["Market"]
    return bc.line(
        oil,
        heading="Oil, gas and coal · share of US shares held",
        suffix="%",
        decimals=1,
        zero=True,
        markers=True,
        dash=["solid", "solid", "solid", "dashed"],
        color=firm_colours(F.FUND_MANAGERS, theme) + [MARKET_COLOUR[theme]],
        theme=theme,
        width=WIDE,
        height=340,
    )


def clean_vs_oil_combo(theme: str) -> bc.Chart:
    clean = year_ends(F.energy_value("clean_energy"))[F.FUND_MANAGERS].sum(axis=1) / 1e9
    oil = year_ends(F.energy_value("oil_gas_coal"))[F.FUND_MANAGERS].sum(axis=1) / 1e9
    df = pd.DataFrame({"Clean energy": clean.round(1), "Oil, gas and coal": oil.round(0)})
    p = palette(theme)
    return bc.combo(
        df,
        bars="Clean energy",
        line="Oil, gas and coal",
        prefix="$",
        suffix="bn",
        line_prefix="$",
        line_suffix="bn",
        line_decimals=0,
        heading="Big Three · clean energy (bars) vs oil, gas and coal (line) · $bn",
        color=[p[2], SECTOR_COLOURS[theme]["Energy"]],
        theme=theme,
        width=WIDE,
        height=340,
    )


def share_parts(row: pd.Series) -> dict[str, float]:
    """Each firm's share in % to one decimal, adding up exactly to the rounded total.

    Plain rounding can make 6.87 + 8.21 + 3.57 show as 18.7 when the total is
    18.6, so the leftover tenths go to the parts that lost the most in rounding.
    """
    exact = {F.short_name(f): float(row[f]) * 100 for f in F.FUND_MANAGERS}
    total = round(sum(exact.values()), 1)
    tenths = {k: int(v * 10) for k, v in exact.items()}
    spare = round(total * 10) - sum(tenths.values())
    for k in sorted(exact, key=lambda k: exact[k] * 10 - tenths[k], reverse=True)[:spare]:
        tenths[k] += 1
    return {k: v / 10 for k, v in tenths.items()}


def market_share_gauge(theme: str) -> bc.Chart:
    share = F.big_three_market_share()
    first_year_end = share[share.index.str.endswith("12-31")].iloc[0]
    now = round(sum(share_parts(share.iloc[-1]).values()), 1)
    then = round(sum(share_parts(first_year_end).values()), 1)
    return bc.gauge(
        now,
        min=0,
        max=30,
        label="of US public company shares",
        suffix="%",
        decimals=1,
        goal=then,
        heading="Big Three combined · end of 2025 · mark = 2015",
        color=[palette(theme)[0]],
        theme=theme,
        width=HALF,
        height=300,
    )


def market_share_area(theme: str) -> bc.Chart:
    share = (F.big_three_market_share() * 100).round(2)
    share.index = pd.to_datetime(share.index)
    share.columns = names(share.columns)
    return bc.area(
        share,
        stacked=True,
        heading="Share of all US public company shares · %",
        suffix="%",
        decimals=1,
        x_format="%Y",
        color=firm_colours(F.FUND_MANAGERS, theme),
        theme=theme,
        width=WIDE,
        height=340,
    )


def market_share_progress(theme: str) -> bc.Chart:
    return bc.progress(
        share_parts(F.big_three_market_share().iloc[-1]),
        max=100,
        suffix="%",
        decimals=1,
        heading="Of every $100 in US public company shares, the Big Three hold",
        color=firm_colours(F.FUND_MANAGERS, theme),
        theme=theme,
        width=WIDE,
    )


def stake_rings(theme: str) -> bc.Chart:
    s = F.stakes()
    snap = s[s["quarter_end"] == s["quarter_end"].max()].head(5)
    labels = {
        "NVIDIA CORPORATION": "Nvidia",
        "APPLE INC": "Apple",
        "MICROSOFT CORP": "Microsoft",
        "AMAZON COM INC": "Amazon",
        "ALPHABET INC": "Alphabet",
    }
    data = {
        labels.get(r.issuer, r.issuer.title()): round(r.stake * 100, 1) for r in snap.itertuples()
    }
    return bc.ring(
        data,
        heading="Big Three stake in the five biggest holdings · % of shares",
        suffix="%",
        decimals=1,
        color=palette(theme)[:5],
        theme=theme,
        width=HALF,
        height=300,
    )


def stake_histogram(theme: str) -> bc.Chart:
    s = F.stakes()
    data = {
        year: (s[s["quarter_end"] == f"{year}-12-31"]["stake"] * 100).round(2).tolist()
        for year in ("2015", "2025")
    }
    p = palette(theme)
    return bc.histogram(
        data,
        bin_width=2.5,
        percent=True,
        mark="median",
        suffix="%",
        heading="Big Three stake across the ~500 largest holdings · share of companies",
        color=[p[4], p[1]],
        theme=theme,
        width=WIDE,
        height=340,
    )


BUILDERS += [
    sector_area,
    sector_shift_bars,
    sector_bullets,
    distance_line,
    oil_line,
    clean_vs_oil_combo,
    market_share_gauge,
    market_share_area,
    market_share_progress,
    stake_rings,
    stake_histogram,
]
NAMES.update(
    {
        sector_area: "f3-sector-mix",
        sector_shift_bars: "f3-sector-shift",
        sector_bullets: "f4-vs-market",
        distance_line: "f4-distance",
        oil_line: "f5-oil-gas-coal",
        clean_vs_oil_combo: "f5-clean-vs-oil",
        market_share_gauge: "f6-market-share-gauge",
        market_share_area: "f6-market-share",
        market_share_progress: "f6-market-share-split",
        stake_rings: "f6-top-stakes",
        stake_histogram: "f6-stakes-spread",
    }
)


# Finding 9: scenarios ---------------------------------------------------------
#
# Forecasts are fan charts: the outer band holds 80% of simulated outcomes
# (bad to good, the 10th to 90th percentile), the inner band 50% (25th to
# 75th) and the dashed line is the central forecast (the median, "middling").

FAN_LABELS = {
    "actual": "Actual",
    "central": "Central forecast",
    "outer": "80% of outcomes",
    "inner": "50% of outcomes",
}
DRIVER_COLOUR = {"market": 2, "rate": 4}  # palette index; firm colours stay on the firms

# Alt text written for the fan charts, by chart name. Bezel Charts' own summary
# counts the years before the forecast starts as missing values, which reads
# like a data gap to a screen reader, so these spell out the numbers instead.
ALTS: dict[str, str] = {}


def fan_alt(heading: str, paths: pd.DataFrame, fmt: Callable[[float], str], actual: bool) -> str:
    end = paths.loc[paths.index.max()]
    first, start = paths.index.min(), 2025
    parts = [f"{heading}. Fan chart."]
    if actual:
        parts.append(
            f"Actual: {fmt(paths.loc[first, 'middling'])} in {first}, "
            f"{fmt(paths.loc[start, 'middling'])} in {start}."
        )
    else:
        parts.append(f"Starts at {fmt(paths.loc[start, 'middling'])} in {start}.")
    parts.append(
        f"Central forecast for {paths.index.max()}: {fmt(end['middling'])}. "
        f"50% of outcomes between {fmt(end['p25'])} and {fmt(end['p75'])}; "
        f"80% between {fmt(end['bad'])} and {fmt(end['good'])}."
    )
    return " ".join(parts)


def soften(colour: str, theme: str, amount: float = 0.45) -> str:
    """Mix a colour towards the tile background, for the outer band of a fan."""
    tile = bc.themes[theme]["tile"]
    a = [int(colour[i : i + 2], 16) for i in (1, 3, 5)]
    b = [int(tile[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * amount):02X}" for x, y in zip(a, b, strict=True))


def fan_frame(paths: pd.DataFrame, start: int = 2025) -> pd.DataFrame:
    """Actual line to the start year, then the central forecast and both bands from it.

    paths has years as rows and bad / p25 / middling / p75 / good as columns,
    with history copied into all of them up to the start year.
    """
    years = paths.index
    df = pd.DataFrame(index=years)
    df[FAN_LABELS["actual"]] = paths["middling"].where(years <= start)
    df[FAN_LABELS["central"]] = paths["middling"].where(years >= start)
    for col in F.FAN:
        df[col] = paths[col].where(years >= start)
    df.index = df.index.astype(str)
    return df


def fan_chart(
    paths: pd.DataFrame, colour: str, theme: str, actual: bool = True, **options
) -> bc.Chart:
    """A fan chart; actual=False for the simulated drivers, which start at 2025."""
    lines = [FAN_LABELS["actual"], FAN_LABELS["central"]] if actual else [FAN_LABELS["central"]]
    return bc.line(
        fan_frame(paths),
        y=lines,
        bands=[
            {
                "name": FAN_LABELS["outer"],
                "low": "bad",
                "high": "good",
                "color": soften(colour, theme),
            },
            {"name": FAN_LABELS["inner"], "low": "p25", "high": "p75", "color": colour},
        ],
        stat="none",
        dash=["solid", "dashed"][-len(lines) :],
        color=[colour] * len(lines),
        theme=theme,
        **options,
    )


def firm_fan(firm: str, metric: str, theme: str, width: int = HALF) -> bc.Chart:
    p = F.scenario_paths(firm, metric)
    if metric == "aum":
        p = (p / 1000).round(2)
        unit, label, decimals = "T", "AUM", 1
    else:
        # Small firms get a decimal place, so the axis doesn't repeat "$3bn".
        small = p["good"].max() < 10
        p = p.round(2 if small else 1)
        unit, decimals = "bn", 1 if small else 0
        label = "profit" if metric == "net_income" else "revenue"
    heading = f"{F.short_name(firm)} · {label} to 2035 · ${unit}"
    name = f"f9-{'aum' if metric == 'aum' else 'profit'}-{firm.replace('_', '-')}"
    ALTS[name] = fan_alt(heading, p, lambda v: f"${v:,.{1 if v < 10 else decimals}f}{unit}", True)
    return fan_chart(
        p,
        palette(theme)[FIRM_COLOUR[firm]],
        theme,
        heading=heading,
        prefix="$",
        suffix=unit,
        decimals=decimals,
        notes={"2025": "Forecast starts"},
        width=width,
        height=300,
    )


def profit_fans(theme: str) -> dict[str, bc.Chart]:
    return {f"f9-profit-{f.replace('_', '-')}": firm_fan(f, "net_income", theme) for f in F.LISTED}


def aum_fans(theme: str) -> dict[str, bc.Chart]:
    return {
        f"f9-aum-{f.replace('_', '-')}": firm_fan(f, "aum", theme)
        for f in ("blackrock", "state_street")
    }


def driver_paths(driver: str, start_value: float) -> pd.DataFrame:
    d = F.driver_scenarios()
    df = pd.DataFrame({s: d[f"{driver}_{s}"] for s in F.FAN})
    df.loc[2025] = start_value
    return df.sort_index()


def profit_2035_bars(theme: str) -> bc.Chart:
    rows = {}
    for firm in F.LISTED:
        p = F.scenario_paths(firm, "net_income")
        rows[F.short_name(firm)] = {
            "2025 actual": p.loc[2025, "middling"],
            "2035 bad": p.loc[2035, "bad"],
            "2035 middling": p.loc[2035, "middling"],
            "2035 good": p.loc[2035, "good"],
        }
    df = pd.DataFrame(rows).T.round(1)
    t = bc.themes[theme]
    return bc.bars(
        df,
        heading="Profit in 2035 under each scenario · $bn",
        prefix="$",
        suffix="bn",
        decimals=0,
        show_values=True,
        color=[MARKET_COLOUR[theme], t["down"], palette(theme)[0], t["up"]],
        patterns=["stripes", "solid", "solid", "solid"],
        theme=theme,
        width=WIDE,
        height=360,
    )


def market_fan(theme: str) -> bc.Chart:
    p = driver_paths("market", 100.0).round(0)
    heading = "US market value · 2025 = 100"
    ALTS["f9-market"] = fan_alt(heading, p, lambda v: f"{v:,.0f}", actual=False)
    return fan_chart(
        p,
        palette(theme)[DRIVER_COLOUR["market"]],
        theme,
        actual=False,
        heading=heading,
        decimals=0,
        width=HALF,
        height=300,
    )


def rate_fan(theme: str) -> bc.Chart:
    rate = F.fed_funds_quarterly()
    last = float(rate.loc["2025Q1":"2025Q4"].mean())
    p = driver_paths("rate", last).round(2)
    heading = "Fed funds rate · yearly average %"
    ALTS["f9-rates"] = fan_alt(heading, p, lambda v: f"{v:.1f}%", actual=False)
    return fan_chart(
        p,
        palette(theme)[DRIVER_COLOUR["rate"]],
        theme,
        actual=False,
        heading=heading,
        suffix="%",
        decimals=1,
        zero=True,
        width=HALF,
        height=300,
    )


def backtest_bullets(theme: str) -> bc.Chart:
    s = F.backtest_summary().reset_index()
    label = {"revenue": "revenue", "net_income": "profit", "aum": "AUM (year-end sum)"}
    s = s[s["metric"] != "aum"]
    df = pd.DataFrame(
        {
            "measure": [
                f"{F.short_name(f)} {label[m]}" for f, m in zip(s["firm"], s["metric"], strict=True)
            ],
            "Model": s["predicted_total"].round(0),
            "What happened": s["actual_total"].round(0),
        }
    )
    return bc.bullet(
        df,
        x="measure",
        y="Model",
        target="What happened",
        series=["Model (trained to 2020)", "What happened"],
        prefix="$",
        suffix="bn",
        decimals=0,
        heading="Backtest 2021-2025 · bar = model (trained to 2020), mark = what happened",
        color=[palette(theme)[0]],
        theme=theme,
        width=WIDE,
        height=440,
    )


def backtest_error_bars(theme: str) -> bc.Chart:
    s = F.backtest_summary()["error"].unstack("metric")[["revenue", "net_income"]] * 100
    s = s.loc[F.LISTED].round(1)
    s.index = names(s.index)
    s.columns = ["Revenue", "Profit"]
    p = palette(theme)
    return bc.bars(
        s,
        heading="Backtest · average yearly error, 2021-2025 · %",
        suffix="%",
        decimals=0,
        show_values=True,
        horizontal=True,
        color=[p[4], p[1]],
        theme=theme,
        width=HALF,
        height=300,
    )


BUILDERS += [
    profit_fans,
    aum_fans,
    profit_2035_bars,
    market_fan,
    rate_fan,
    backtest_bullets,
    backtest_error_bars,
]
NAMES.update(
    {
        profit_2035_bars: "f9-profit-2035",
        market_fan: "f9-market",
        rate_fan: "f9-rates",
        backtest_bullets: "f9-backtest",
        backtest_error_bars: "f9-backtest-error",
    }
)
