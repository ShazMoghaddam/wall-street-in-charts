# Changelog

All notable changes to this project are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [semantic versioning](https://semver.org/).

## [1.0.0] - 2026-11-26

The full report: nine findings on six Wall Street giants (JPMorgan, Goldman Sachs, Morgan Stanley, BlackRock, Vanguard, State Street) from SEC filings, 2015 to 2025, with scenarios to 2035. Built in five stages.

### Report site and polish (stage 5)
- Report site on GitHub Pages (`docs/`): one long page with all nine findings, a contents bar, light and dark charts, a phone layout and sharing tags. Built by `findings/build.py`, so it always matches the findings.
- README banner and GitHub social preview in the "Ledger" style, drawn from the data by `assets/build.py`.
- README contents, "How it's built" section and a link to the live report.
- Site tests: every chart present, alt text on every image, accessibility basics and matching headline numbers. CI checks `docs/` is up to date.
- The Big Three's market share is shown to one decimal place everywhere (18.6%), and the per-firm split is rounded so the parts always add up to the total.

### Forecasts (stage 4)
- Finding 9: good, middling and bad scenarios to 2030 and 2035 for revenue, profit and AUM, from driver models and 10,000 Monte Carlo futures built from real 1990-2025 history.
- Backtest: models trained on 2015-2020 predict 2021-2025, with real drivers and fully simulated.
- `models/run.py` and `wallstreet/forecast.py`, with a fixed seed so results repeat; CI checks the committed outputs match a fresh run.
- Bullet chart legends now name what the bar and the mark show (they read "Actual" and "Target").

### Holdings and sectors (stage 3)
- Findings 3 to 6: where the fund managers invest, whether they choose or follow the market, energy holdings since 2015, and the Big Three's share of the US stock market.
- Sector mapping for 13F holdings: SEC company match, SIC code to 11 sectors, hand checks for the largest holdings, ETFs kept apart. At least 95% of value mapped in every quarter.
- The institutional "market" from the SEC's bulk 13F data, one year-end per year, with unit-slip checks against the Big Three's own prices.
- Big Three stakes in their ~500 largest holdings, using shares outstanding from the SEC.

### History findings (stage 2)
- Findings 1, 2, 7 and 8: who grew biggest, where the banks make money, how profits moved when rates rose, and the shocks of 2020, 2022 and 2023.
- `findings/build.py` writes the charts, one page per finding and the README headline block from the data, so text and numbers never drift apart.
- Charts in light and dark, shown in the README with GitHub's `<picture>` tag; all 15 Bezel Charts types used across the project.
- Net interest income for the banks and State Street, and Vanguard AUM points from Vanguard's own sites.
- Tests that fail if a data refresh makes a sentence in the findings untrue.

### Data pipeline (stage 1)
- `data/fetch.py` with a cached, rate-limited SEC and FRED client; secrets read from the environment only.
- Quarterly revenue, net income and total assets for the five listed firms, with Q4 worked out from annual figures.
- Bank segment revenue and profit from 10-K XBRL, mapped to three business buckets.
- Quarterly AUM for BlackRock and State Street from SEC earnings releases.
- 13F holdings for BlackRock, Vanguard and State Street, handling the 2023 value-unit change, restatements, BlackRock's subsidiary filings before 2017 and its 2024 change of SEC ID.
- Notebooks, unit tests, offline data checks, MIT licence, security policy, contribution guide, Dependabot and CI.
