"""Build the charts and the findings text from data/processed/.

Usage (from the repo root):

    python findings/build.py

Writes:
- charts/<name>-light.svg and charts/<name>-dark.svg
- findings/numbers.json, every number the text quotes
- findings/NN-*.md, one page per finding
- the headline findings block in README.md, between the findings markers

Every number in the text is filled in from wallstreet.findings, so rebuilding
after a data refresh updates the words as well as the charts.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from wallstreet import charts as C  # noqa: E402
from wallstreet import findings as F  # noqa: E402

CHARTS = ROOT / "charts"
FINDINGS = ROOT / "findings"
README = ROOT / "README.md"
START, END = "<!-- findings:start -->", "<!-- findings:end -->"


# Formatting -----------------------------------------------------------------


def bn(x: float) -> str:
    return f"${x:,.1f}bn"


def tn(x: float) -> str:
    return f"${x:,.1f} trillion"


def pct(x: float, signed: bool = False) -> str:
    value = round(x * 100)
    if signed:
        return f"{'+' if value > 0 else '−' if value < 0 else ''}{abs(value)}%"
    return f"{value}%"


def times(x: float) -> str:
    return f"{x:.1f}×"


def picture(name: str, alt: str, width: int, base: str = "charts") -> str:
    """A <picture> that shows the dark chart to readers using GitHub's dark theme."""
    alt = alt.replace('"', "'")
    return (
        "<picture>\n"
        f'  <source media="(prefers-color-scheme: dark)" srcset="{base}/{name}-dark.svg">\n'
        f'  <img src="{base}/{name}-light.svg" alt="{alt}" width="{width}">\n'
        "</picture>"
    )


# Pages ----------------------------------------------------------------------


def page_growth(n: dict, alts: dict, base: str) -> str:
    g = F.growth_table().sort_values("profit_multiple", ascending=False)
    top, second = g.index[0], g.index[1]
    lines = [
        "# 1. Who grew biggest?",
        "",
        "Revenue, profit and assets for the five listed firms, 2015 to 2025, plus assets "
        "under management (AUM) for the three fund managers.",
        "",
        picture("f1-revenue", alts["f1-revenue"], 760, base),
        "",
        f"- **JPMorgan is in a league of its own.** Revenue rose from "
        f"{bn(n['jpmorgan_revenue_2015_bn'])} to {bn(n['jpmorgan_revenue_2025_bn'])}, more "
        f"than the other four firms put together.",
        f"- **{F.short_name(top)} and {F.short_name(second)} grew profit fastest.** "
        f"{F.short_name(top)}'s profit is {times(g.loc[top, 'profit_multiple'])} its 2015 level "
        f"and {F.short_name(second)}'s is {times(g.loc[second, 'profit_multiple'])}, both ahead "
        f"of JPMorgan's {times(n['jpmorgan_profit_multiple'])}.",
        f"- **BlackRock doubled its revenue ({times(n['blackrock_revenue_multiple'])}) but "
        f"profit grew less ({times(n['blackrock_profit_multiple'])}),** so its profit margin "
        f"narrowed.",
        f"- **State Street grew slowest,** with profit up {times(n['state_street_profit_multiple'])}.",
        "",
        picture("f1-profit-growth", alts["f1-profit-growth"], 372, base),
        picture("f1-vanguard-aum", alts["f1-vanguard-aum"], 372, base),
        "",
        "## Assets under management",
        "",
        f"BlackRock's AUM tripled, from {tn(n['blackrock_aum_2015q4'])} at the end of 2015 to "
        f"{tn(n['blackrock_aum_2025q4'])} at the end of 2025. State Street's grew from "
        f"{tn(n['state_street_aum_2015q4'])} to {tn(n['state_street_aum_2025q4'])}. Vanguard is "
        f"private and publishes AUM only now and then; its latest figure is "
        f"{tn(n['vanguard_aum_2025'])}.",
        "",
        picture("f1-aum", alts["f1-aum"], 760, base),
        "",
        "## The banks' balance sheets",
        "",
        " ".join(
            picture(
                f"f1-assets-{f.replace('_', '-')}",
                alts[f"f1-assets-{f.replace('_', '-')}"],
                244,
                base,
            )
            for f in F.BANKS
        ),
        "",
        "## Notes",
        "",
        "- Revenue for the banks is net of interest expense, the way they report it.",
        "- Profit is net income for the year. AUM is not comparable with the banks' total "
        "assets: AUM is clients' money, total assets is the bank's own balance sheet.",
        "- Vanguard's points are only the dates Vanguard (or a press report of Vanguard's figure) "
        "published. Gaps are left as gaps. Sources are in `data/manual/vanguard_aum.csv`.",
    ]
    return "\n".join(lines) + "\n"


def page_segments(n: dict, alts: dict, base: str) -> str:
    j = {b: n[f"jpmorgan_{b}_share_2025"] for b in F.BUCKETS}
    g = {b: n[f"goldman_{b}_share_2025"] for b in F.BUCKETS}
    m = {b: n.get(f"morgan_stanley_{b}_share_2025", 0) for b in F.BUCKETS}
    lines = [
        "# 2. Where do the banks make their money?",
        "",
        "Each bank's revenue split into three kinds of business: **Markets** (trading and "
        "dealmaking), **Wealth** (wealth and asset management) and **Lending** (consumer and "
        "business banking).",
        "",
        " ".join(
            picture(
                f"f2-mix-{f.replace('_', '-')}", alts[f"f2-mix-{f.replace('_', '-')}"], 244, base
            )
            for f in F.BANKS
        ),
        "",
        f"- **Goldman is still a markets firm.** {pct(g['markets_dealmaking'])} of its 2025 revenue "
        f"came from trading and dealmaking. Its push into consumer banking (Marcus, the Apple "
        f"Card) is being wound down, and lending is now {pct(g['banking_lending'])}.",
        f"- **Morgan Stanley is now more wealth manager than trader.** {pct(m['wealth_asset_management'])} "
        f"of revenue came from wealth and asset management, after buying E*TRADE (2020) and "
        f"Eaton Vance (2021).",
        f"- **JPMorgan is the most balanced:** {pct(j['markets_dealmaking'])} markets, "
        f"{pct(j['banking_lending'])} lending and {pct(j['wealth_asset_management'])} wealth.",
        "",
        picture("f2-segments-jpmorgan", alts["f2-segments-jpmorgan"], 760, base),
        "",
        "**Regrouping:** from 2022, JPMorgan reports its commercial bank inside the investment "
        "bank, so part of its lending moves into Markets from that year. The jump in 2022 is "
        "a change of grouping, not of business.",
        "",
        picture("f2-segments-goldman", alts["f2-segments-goldman"], 760, base),
        "",
        "**Regrouping:** Goldman reorganised in 2020 and again in 2022. From 2020 the figures "
        "use its current three segments, restated by Goldman.",
        "",
        picture("f2-segments-morgan-stanley", alts["f2-segments-morgan-stanley"], 760, base),
        "",
        "## Notes",
        "",
        "- Segment figures come from each bank's 10-K. Each year uses the newest 10-K that "
        "reports it, so years near a reorganisation use restated figures.",
        "- The mapping from each bank's segment names to the three groups is in "
        "`data/manual/segment_map.csv`.",
        "- JPMorgan's segment figures are on its 'managed basis' and leave out its corporate "
        "centre, so they add up to slightly more or less than reported revenue.",
    ]
    return "\n".join(lines) + "\n"


def page_rates(n: dict, alts: dict, base: str) -> str:
    lines = [
        "# 7. How did profits move when rates rose in 2022?",
        "",
        f"The Federal Reserve raised its main interest rate from an average of "
        f"{n['fed_funds_2021_avg']:.2f}% in 2021 to {n['fed_funds_2023_avg']:.1f}% in 2023, the "
        f"fastest rise in forty years. Here is what happened to profit between 2021 and 2023.",
        "",
        picture("f7-profit-and-rates", alts["f7-profit-and-rates"], 760, base),
        "",
        f"- **JPMorgan's net interest income jumped {pct(n['jpmorgan_nii_change_2021_2023_pct'])},** "
        f"from {bn(n['jpmorgan_nii_2021_bn'])} to {bn(n['jpmorgan_nii_2023_bn'])}. It earned more "
        f"on loans while paying little more on deposits. Its profit still rose "
        f"{pct(n['jpmorgan_profit_change_2021_2023_pct'])} while the others fell.",
        f"- **Goldman's profit fell {pct(-n['goldman_profit_change_2021_2023_pct'])}** and Morgan "
        f"Stanley's {pct(-n['morgan_stanley_profit_change_2021_2023_pct'])}. 2021 was a record "
        f"year for deals; higher rates slowed mergers and share sales, and their interest "
        f"income barely moved ({pct(n['goldman_nii_change_2021_2023_pct'], True)} and "
        f"{pct(n['morgan_stanley_nii_change_2021_2023_pct'], True)}).",
        f"- **Fund managers felt falling markets, not rates.** BlackRock's profit fell "
        f"{pct(-n['blackrock_profit_change_2021_2023_pct'])} as lower share prices cut its fees. "
        f"State Street's fell {pct(-n['state_street_profit_change_2021_2023_pct'])}, even though "
        f"its interest income rose {pct(n['state_street_nii_change_2021_2023_pct'])}.",
        "",
        picture("f7-profit-waterfall", alts["f7-profit-waterfall"], 760, base),
        "",
        picture("f7-net-interest-income", alts["f7-net-interest-income"], 372, base),
        picture("f7-nii-vs-rates", alts["f7-nii-vs-rates"], 372, base),
        "",
        "## Notes",
        "",
        "- Net interest income is interest earned minus interest paid (XBRL tag "
        "`InterestIncomeExpenseNet`). BlackRock does not report it.",
        "- In the scatter, each firm's net interest income is indexed to its 2019 average (= 100), "
        "so firms of very different sizes share one scale. Each dot is one quarter.",
    ]
    return "\n".join(lines) + "\n"


def page_shocks(n: dict, alts: dict, base: str) -> str:
    lines = [
        "# 8. Shocks: 2020, the 2022 rate rises and the 2023 bank failures",
        "",
        "Profit in each shock against the same quarters a year earlier: the first half of 2020, "
        "the whole of 2022, and the first half of 2023 (when Silicon Valley Bank, Signature and "
        "First Republic failed).",
        "",
        picture("f8-shocks", alts["f8-shocks"], 760, base),
        "",
        f"- **The pandemic hit the lenders.** JPMorgan's profit fell "
        f"{pct(-n['jpmorgan_covid_change_pct'])} and Goldman's {pct(-n['goldman_covid_change_pct'])} "
        f"as they set money aside for loans that might go bad. State Street's rose "
        f"{pct(n['state_street_covid_change_pct'])}, helped by busy markets.",
        f"- **2022 hit almost everyone,** led by Goldman ({pct(n['goldman_rates_change_pct'], True)}).",
        f"- **The 2023 bank failures split the big banks.** JPMorgan's profit rose "
        f"{pct(n['jpmorgan_banks_change_pct'])}, helped by higher interest income and by buying "
        f"First Republic in May 2023. Goldman's fell {pct(-n['goldman_banks_change_pct'])}.",
        "",
        picture("f8-stress-days-2020", alts["f8-stress-days-2020"], 760, base),
        "",
        f"The VIX, Wall Street's 'fear gauge', closed above {F.STRESS_LEVEL} on "
        f"{n['stress_days_2020']} trading days in 2020 and peaked at {n['vix_2020_peak']:.0f} on "
        f"{n['vix_2020_peak_date']}. It did so on {n['stress_days_2022']} days in 2022 and "
        f"{'not once' if n['stress_days_2023'] == 0 else str(n['stress_days_2023']) + ' days'} "
        f"in 2023: the bank failures shook banks far more than the wider market.",
        "",
        picture("f8-margin-spread", alts["f8-margin-spread"], 760, base),
        "",
        "Profit margins by quarter, 2015 to 2025. A taller box means a less predictable "
        f"business. {F.short_name(n['widest_margin_spread'])} swings the most.",
        "",
        "## Notes",
        "",
        "- Each shock compares the same quarters a year apart, so seasonal patterns cancel out.",
        "- Days of market stress use FRED's daily VIX close (series `VIXCLS`).",
    ]
    return "\n".join(lines) + "\n"


PAGES = [
    ("01-who-grew-biggest.md", page_growth),
    ("02-where-banks-make-money.md", page_segments),
    ("07-rates-and-profits.md", page_rates),
    ("08-shocks.md", page_shocks),
]


def readme_block(n: dict, alts: dict) -> str:
    g = F.growth_table().sort_values("profit_multiple", ascending=False)
    top = g.index[0]
    return "\n".join(
        [
            START,
            "## Headline findings so far",
            "",
            picture("f1-revenue", alts["f1-revenue"], 760),
            "",
            f"1. **[Who grew biggest](findings/01-who-grew-biggest.md):** JPMorgan's revenue "
            f"nearly doubled to {bn(n['jpmorgan_revenue_2025_bn'])}, but "
            f"{F.short_name(top)} grew profit fastest ({times(g.loc[top, 'profit_multiple'])} its "
            f"2015 level). BlackRock's AUM tripled to {tn(n['blackrock_aum_2025q4'])}.",
            f"2. **[Where the banks make money](findings/02-where-banks-make-money.md):** "
            f"Goldman still earns {pct(n['goldman_markets_dealmaking_share_2025'])} of revenue "
            f"from markets; Morgan Stanley now earns most of its revenue "
            f"({pct(n['morgan_stanley_wealth_asset_management_share_2025'])}) from wealth.",
            f"3. **[Rates rose in 2022](findings/07-rates-and-profits.md):** JPMorgan's net "
            f"interest income jumped {pct(n['jpmorgan_nii_change_2021_2023_pct'])} from 2021 to "
            f"2023, while Goldman's profit fell {pct(-n['goldman_profit_change_2021_2023_pct'])}.",
            f"4. **[Shocks](findings/08-shocks.md):** the pandemic cut JPMorgan's first-half "
            f"profit by {pct(-n['jpmorgan_covid_change_pct'])}; the 2023 bank failures lifted it "
            f"{pct(n['jpmorgan_banks_change_pct'])}.",
            "",
            picture("f7-profit-and-rates", alts["f7-profit-and-rates"], 760),
            "",
            "Findings 3 to 6 (holdings and sectors) and 9 (forecasts) arrive in later stages.",
            END,
        ]
    )


def main() -> None:
    CHARTS.mkdir(exist_ok=True)
    alts: dict[str, str] = {}
    for name, themes in C.build_all().items():
        for theme, chart in themes.items():
            chart.save(str(CHARTS / f"{name}-{theme}.svg"))
        alts[name] = themes["light"].alt
    print(f"wrote {len(alts) * 2} charts to charts/")

    numbers = F.headline_numbers()
    clean = {k: (round(v, 6) if isinstance(v, float) else v) for k, v in numbers.items()}
    clean = {k: (float(v) if hasattr(v, "item") else v) for k, v in clean.items()}
    (FINDINGS / "numbers.json").write_text(json.dumps(clean, indent=2, sort_keys=True) + "\n")

    for filename, builder in PAGES:
        (FINDINGS / filename).write_text(builder(numbers, alts, "../charts"))
        print(f"wrote findings/{filename}")

    readme = README.read_text()
    block = readme_block(numbers, alts)
    if START in readme:
        readme = re.sub(re.escape(START) + ".*?" + re.escape(END), block, readme, flags=re.S)
    else:
        readme = readme.replace("## The questions", block + "\n\n## The questions", 1)
    README.write_text(readme)
    print("updated README.md findings block")


if __name__ == "__main__":
    main()
