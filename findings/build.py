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


def page_sectors(n: dict, alts: dict, base: str) -> str:
    lines = [
        "# 3. Where do the fund managers invest?",
        "",
        "The sector mix of the US-listed shares that BlackRock, Vanguard and State Street "
        "report in their 13F filings, combined, at each year-end.",
        "",
        picture("f3-sector-mix", alts["f3-sector-mix"], 760, base),
        "",
        f"- **Technology took over.** It rose from {pct(n['tech_share_2015'])} of the Big Three's "
        f"holdings in 2015 to {pct(n['tech_share_2025'])} in 2025, by far the largest sector.",
        f"- **Most other sectors shrank to make room,** above all {n['biggest_fallers']}.",
        "- **They didn't choose this.** It is what happened to the market itself as Apple, "
        "Microsoft, Nvidia and the rest grew (see finding 4).",
        "",
        picture("f3-sector-shift", alts["f3-sector-shift"], 760, base),
        "",
        "## Notes",
        "",
        "- **US-listed shares only.** 13F filings leave out bonds, cash, private assets and "
        "shares listed outside the US.",
        f"- **Sectors** come from each company's SEC industry code (SIC), grouped into 11 "
        f"sectors close to the GICS sectors index providers use. The largest holdings were "
        f"checked by hand (`data/manual/sector_overrides.csv`), for example Alphabet and Meta "
        f"as Communication and Visa as Financials. At least {pct(n['mapped_share_min'])} of "
        f"each firm's value is mapped in every quarter.",
        "- **ETFs** held inside the filings are left out of the mix, since each is a basket "
        "of other companies.",
    ]
    return "\n".join(lines) + "\n"


def page_following(n: dict, alts: dict, base: str) -> str:
    lines = [
        "# 4. Choosing, or just following the market?",
        "",
        "Each firm's sector mix compared with the 'market': every 13F filer's holdings added "
        "up, which is the institutional market (around 4,000 to 9,000 managers a year).",
        "",
        picture("f4-vs-market", alts["f4-vs-market"], 760, base),
        "",
        f"- **They follow the market almost exactly.** In 2025 no firm's sector mix was more "
        f"than {pct(n['max_distance_2025'])} away from the market's (0% would be an exact copy).",
        f"- **The Big Three hold a little more technology** ({pct(n['tech_share_2025'])} against "
        f"{pct(n['market_tech_share_2025'])}), most likely because index funds hold the "
        f"biggest companies in full, while other managers spread more into smaller ones.",
        f"- **The one clear tilt was Vanguard's real estate in 2015:** "
        f"{pct(n['vanguard_real_estate_2015'])} against the market's "
        f"{pct(n['market_real_estate_2015'])}, from its large property (REIT) index funds.",
        "",
        picture("f4-distance", alts["f4-distance"], 372, base),
        "",
        "## How the distance is measured",
        "",
        "Add up the gaps between a firm's weight and the market's weight in each of the 11 "
        "sectors, then halve it. That is the share of the portfolio that would have to move "
        "to match the market. 0% is an exact copy; 100% would mean no overlap at all.",
        "",
        "## Notes",
        "",
        "- The market is built from the SEC's bulk 13F data, one year-end per year. Some "
        "filers report in the wrong units; those rows are fixed or left out using a price "
        "check against the Big Three's own filings (see `data/README.md`).",
    ]
    return "\n".join(lines) + "\n"


def page_energy(n: dict, alts: dict, base: str) -> str:
    lines = [
        "# 5. Energy then and now",
        "",
        "Oil, gas and coal companies, and a hand-made list of clean energy companies, in the "
        "Big Three's holdings since 2015.",
        "",
        picture("f5-oil-gas-coal", alts["f5-oil-gas-coal"], 760, base),
        "",
        f"- **Oil, gas and coal halved as a share.** BlackRock went from "
        f"{pct(n['blackrock_oil_2015'])} to {pct(n['blackrock_oil_2025'])}, Vanguard from "
        f"{pct(n['vanguard_oil_2015'])} to {pct(n['vanguard_oil_2025'])} and State Street from "
        f"{pct(n['state_street_oil_2015'])} to {pct(n['state_street_oil_2025'])}. The market "
        f"fell the same way ({pct(n['market_oil_2015'])} to {pct(n['market_oil_2025'])}), so "
        f"this is falling energy share prices and booming tech, not selling.",
        "- **2022 shows it:** energy's share jumped when oil and gas prices spiked after Russia "
        "invaded Ukraine, then slid back.",
        f"- **Clean energy stays tiny.** The Big Three's clean energy holdings peaked at "
        f"{bn(n['clean_value_peak_bn'])} and were {bn(n['clean_value_2025_bn'])} at the end of "
        f"2025, against {bn(n['oil_value_2025_bn'])} in oil, gas and coal.",
        "",
        picture("f5-clean-vs-oil", alts["f5-clean-vs-oil"], 760, base),
        "",
        "## Notes",
        "",
        "- **Oil, gas and coal** is the Energy sector: producers, oil services, refiners, "
        "pipelines and coal, by SEC industry code.",
        "- **Clean energy** is a list of 31 US-listed companies whose main business is "
        "solar, wind, geothermal, fuel cells, storage or renewable power, each with a reason "
        "(`data/manual/clean_energy.csv`). Big utilities with large renewable fleets, such as "
        "NextEra Energy, stay in Utilities because most of their business is still a utility.",
        "- **Tesla is left out** of clean energy on purpose: it is a carmaker, and at its "
        "size it would swamp every other name.",
    ]
    return "\n".join(lines) + "\n"


def page_share(n: dict, alts: dict, base: str) -> str:
    lines = [
        "# 6. How much of the US stock market do the Big Three hold?",
        "",
        "BlackRock, Vanguard and State Street's holdings of company shares, as a share of the "
        "total value of all US public company shares (Federal Reserve figures).",
        "",
        picture("f6-market-share-gauge", alts["f6-market-share-gauge"], 372, base),
        picture("f6-top-stakes", alts["f6-top-stakes"], 372, base),
        "",
        f"- **Almost a fifth of the market.** Together they held {pct(n['big_three_share_2025'])} "
        f"of all US public company shares at the end of 2025, up from "
        f"{pct(n['big_three_share_2015'])} in 2015.",
        f"- **Vanguard is the largest** ({n['vanguard_market_share_2025'] * 100:.1f}%), then "
        f"BlackRock ({n['blackrock_market_share_2025'] * 100:.1f}%) and State Street "
        f"({n['state_street_market_share_2025'] * 100:.1f}%).",
        f"- **In the biggest companies the stake is larger.** The typical (median) Big Three stake "
        f"in their ~500 largest holdings rose from {pct(n['median_stake_2015'])} to "
        f"{pct(n['median_stake_2025'])}. They owned more than a fifth of "
        f"{n['stakes_over_20pct_2025']} of those companies in 2025, against "
        f"{n['stakes_over_20pct_2015']} in 2015.",
        "",
        picture("f6-market-share", alts["f6-market-share"], 760, base),
        "",
        picture("f6-market-share-split", alts["f6-market-share-split"], 760, base),
        "",
        picture("f6-stakes-spread", alts["f6-stakes-spread"], 760, base),
        "",
        "## Notes",
        "",
        "- **Market value** is the Fed's figure for all US public companies' shares "
        "(FRED series `BOGZ1LM883164115Q`). 13F filings also include some foreign companies "
        "listed in the US, so the share is a close estimate rather than exact.",
        "- **Stakes** divide the Big Three's combined shares by each company's shares "
        "outstanding from SEC filings. Share classes are added up (Alphabet A and C). "
        "Berkshire Hathaway is left out because one class A share is worth 1,500 class B "
        "shares. About 7 to 10% of the largest holdings have no usable share count.",
        "- **Holding is not owning outright:** the Big Three hold these shares for the people "
        "and pension funds invested in their funds.",
    ]
    return "\n".join(lines) + "\n"


def page_scenarios(n: dict, alts: dict, base: str) -> str:
    def rng(firm: str, metric: str, year: int) -> str:
        return (
            f"{bn(n[f'{firm}_{metric}_{year}_bad_bn'])} (bad), "
            f"{bn(n[f'{firm}_{metric}_{year}_middling_bn'])} (middling) and "
            f"{bn(n[f'{firm}_{metric}_{year}_good_bn'])} (good)"
        )

    below = [F.short_name(f) for f in n["profit_2035_bad_below_2025"]]
    below_text = ", ".join(below[:-1]) + " and " + below[-1] if len(below) > 1 else below[0]
    lines = [
        "# 9. Good, middling and bad scenarios to 2030 and 2035",
        "",
        "> **Not financial advice.** These are illustrations from a deliberately simple model, "
        "not predictions or recommendations. The future will not look like any single line here.",
        "",
        "Each firm is linked by a simple model to the things that move it: the stock market, "
        "interest rates and market volatility. We then run 10,000 simulated futures for those "
        "drivers, built from real stretches of history since 1990 (including the 2000, 2008, "
        "2020 and 2022 shocks), and push each one through the firm models. **Bad, middling and "
        "good are the 10th, 50th and 90th percentiles** of the results: 1 in 10 futures came "
        "out worse than 'bad', and 1 in 10 better than 'good'.",
        "",
        picture("f9-profit-2035", alts["f9-profit-2035"], 760, base),
        "",
        f"- **JPMorgan stays far ahead.** Its 2035 profit comes out at "
        f"{rng('jpmorgan', 'net_income', 2035)}, against {bn(n['jpmorgan_net_income_2025_bn'])} "
        f"in 2025.",
        f"- **The range is wide, and that is the honest answer.** In the bad case, 2035 profit is "
        f"below its 2025 level for {below_text}.",
        f"- **Goldman and Morgan Stanley have the widest ranges** relative to their size, "
        f"because trading and dealmaking swing with markets. Goldman's 2035 profit: "
        f"{rng('goldman', 'net_income', 2035)}.",
        f"- **BlackRock's AUM** reaches ${n['blackrock_aum_2035_middling_tn']:.0f} trillion in "
        f"the middling case (from ${n['blackrock_aum_2025_tn']:.0f} trillion), with a range of "
        f"${n['blackrock_aum_2035_bad_tn']:.0f} to ${n['blackrock_aum_2035_good_tn']:.0f} "
        f"trillion.",
        "",
        " ".join(
            picture(
                f"f9-profit-{f.replace('_', '-')}",
                alts[f"f9-profit-{f.replace('_', '-')}"],
                372,
                base,
            )
            for f in F.LISTED
        ),
        "",
        picture("f9-aum-blackrock", alts["f9-aum-blackrock"], 372, base),
        picture("f9-aum-state-street", alts["f9-aum-state-street"], 372, base),
        "",
        "## The drivers",
        "",
        f"In the middling case the US stock market's total value grows about as fast as it did "
        f"from 1990 to 2025 (about {pct(n['market_growth_per_year_history'])} a year, including "
        f"new listings), reaching "
        f"{n['market_2035_middling'] / 100:.1f} times its 2025 level by 2035. The bad case is "
        f"{n['market_2035_bad'] / 100:.1f} times and the good case {n['market_2035_good'] / 100:.1f} "
        f"times. The Fed funds rate is pulled back towards its long-run level, about "
        f"{n['rate_long_run_mean']:.0f}% as estimated from 1990-2025, with real surprises along the way.",
        "",
        picture("f9-market", alts["f9-market"], 372, base),
        picture("f9-rates", alts["f9-rates"], 372, base),
        "",
        "## Backtest: how close did it get?",
        "",
        "We trained the same models on 2015 to 2020 only, then asked them about 2021 to 2025.",
        "",
        f"- **With the real market and rates fed in**, yearly revenue was off by "
        f"{pct(n['backtest_revenue_error_min'])} to {pct(n['backtest_revenue_error_max'])} on "
        f"average. Profit is harder: from {pct(n['jpmorgan_backtest_profit_error'])} for JPMorgan "
        f"to {pct(n['goldman_backtest_profit_error'])} for Goldman, whose 2021 deal boom and 2023 "
        f"slump no simple model would call.",
        f"- **With everything simulated**, what actually happened landed inside the bad-to-good "
        f"range {pct(n['backtest_inside_share'])} of the time. A well-judged 10th-to-90th range "
        f"should catch about 80%.",
        "",
        picture("f9-backtest", alts["f9-backtest"], 760, base),
        "",
        picture("f9-backtest-error", alts["f9-backtest-error"], 372, base),
        "",
        "## How the models work",
        "",
        "- **Banks:** net interest income follows interest rates and the size of the market; "
        "other revenue (trading, deals, wealth) follows the market and volatility, with "
        "quarter-of-year effects; profit margin follows rates and volatility.",
        "- **Fund managers:** AUM follows the market plus a steady trend (new client money); "
        "revenue follows AUM and rates; profit margin follows rates and volatility.",
        "- **Errors are simulated too.** Each model's leftover error persists from quarter to "
        "quarter, as it does in real life, so the range reflects how wrong the model has been.",
        "- **Vanguard is left out:** its 11 published AUM figures are too few for a model.",
        "- Everything is in `wallstreet/forecast.py`; outputs and settings (including the fixed "
        "random seed) are in `models/`.",
        "",
        "## Limits",
        "",
        "- Ten years is a long way. Mergers (like BlackRock's 2024 and 2025 deals), new rules "
        "or a new business line can change a firm in ways no driver captures.",
        "- 'Good' and 'bad' describe profit and AUM, not whether an outcome is good for anyone else.",
        "- The models are deliberately simple so that every link can be read and checked.",
    ]
    return "\n".join(lines) + "\n"


PAGES = [
    ("01-who-grew-biggest.md", page_growth),
    ("02-where-banks-make-money.md", page_segments),
    ("03-where-fund-managers-invest.md", page_sectors),
    ("04-choosing-or-following.md", page_following),
    ("05-energy.md", page_energy),
    ("06-big-three-share.md", page_share),
    ("07-rates-and-profits.md", page_rates),
    ("08-shocks.md", page_shocks),
    ("09-scenarios.md", page_scenarios),
]


def readme_block(n: dict, alts: dict) -> str:
    g = F.growth_table().sort_values("profit_multiple", ascending=False)
    top = g.index[0]
    return "\n".join(
        [
            START,
            "## Headline findings",
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
            f"3. **[Where the fund managers invest](findings/03-where-fund-managers-invest.md):** "
            f"technology rose from {pct(n['tech_share_2015'])} to {pct(n['tech_share_2025'])} "
            f"of the Big Three's US shares.",
            f"4. **[Choosing or following?](findings/04-choosing-or-following.md):** following. "
            f"No firm's sector mix was more than {pct(n['max_distance_2025'])} away from the "
            f"market's in 2025.",
            f"5. **[Energy](findings/05-energy.md):** oil, gas and coal fell from about "
            f"{pct(n['energy_share_2015'])} to {pct(n['energy_share_2025'])} of their holdings; "
            f"clean energy peaked at just {bn(n['clean_value_peak_bn'])}.",
            f"6. **[The Big Three's share](findings/06-big-three-share.md):** together they held "
            f"{pct(n['big_three_share_2025'])} of all US public company shares at the end of "
            f"2025, up from {pct(n['big_three_share_2015'])} in 2015.",
            f"7. **[Rates rose in 2022](findings/07-rates-and-profits.md):** JPMorgan's net "
            f"interest income jumped {pct(n['jpmorgan_nii_change_2021_2023_pct'])} from 2021 to "
            f"2023, while Goldman's profit fell {pct(-n['goldman_profit_change_2021_2023_pct'])}.",
            f"8. **[Shocks](findings/08-shocks.md):** the pandemic cut JPMorgan's first-half "
            f"profit by {pct(-n['jpmorgan_covid_change_pct'])}; the 2023 bank failures lifted it "
            f"{pct(n['jpmorgan_banks_change_pct'])}.",
            "",
            f"9. **[Scenarios to 2035](findings/09-scenarios.md):** in the middling case "
            f"JPMorgan's profit reaches {bn(n['jpmorgan_net_income_2035_middling_bn'])} by 2035 "
            f"(range {bn(n['jpmorgan_net_income_2035_bad_bn'])} to "
            f"{bn(n['jpmorgan_net_income_2035_good_bn'])}). In a backtest trained to 2020, what "
            f"happened in 2021-2025 fell inside the range {pct(n['backtest_inside_share'])} of "
            f"the time. *Not financial advice.*",
            "",
            picture("f6-market-share", alts["f6-market-share"], 760),
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
