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
