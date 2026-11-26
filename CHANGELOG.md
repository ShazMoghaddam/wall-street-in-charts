# Changelog

All notable changes to this project are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [semantic versioning](https://semver.org/).

## [Unreleased]

### Added
- Finding 9: good, middling and bad scenarios to 2030 and 2035 for revenue, profit and AUM, from driver models and 10,000 Monte Carlo futures built from real 1990-2025 history.
- Backtest: models trained on 2015-2020 predict 2021-2025, with real drivers and fully simulated.
- `models/run.py` and `wallstreet/forecast.py`, with a fixed seed so results repeat; CI checks the committed outputs match a fresh run.
- 12 more charts in light and dark (scenario lines, 2035 profit, drivers, backtest).
- Notebook `notebooks/04_forecasts.ipynb` and `models/README.md`.

### Fixed
- Bullet chart legends now name what the bar and the mark show (they read "Actual" and "Target").
- Holdings findings 3 to 6: where the fund managers invest, whether they choose or follow the market, energy holdings since 2015, and the Big Three's share of the US stock market.
- Sector mapping for 13F holdings: SEC company match, SIC code to 11 sectors, hand checks for the largest holdings, ETFs kept apart. At least 95% of value mapped in every quarter.
- The institutional "market" from the SEC's bulk 13F data, one year-end per year, with unit-slip checks against the Big Three's prices.
- Big Three stakes in their ~500 largest holdings, using shares outstanding from the SEC frames API.
- 11 more charts in light and dark, adding gauge, ring, progress, bullet and histogram, so all 15 Bezel Charts types are now used.
- Notebook `notebooks/03_holdings_and_sectors.ipynb`.
- History findings 1, 2, 7 and 8: who grew biggest, where the banks make money, how profits moved when rates rose, and the shocks of 2020, 2022 and 2023.
- 20 Bezel Charts in light and dark themes (40 SVGs) using ten chart types, shown in the README with GitHub's `<picture>` tag so readers see the theme that matches theirs.
- `findings/build.py`, which writes the charts, one page per finding and the README headline block from the data, so text and numbers never drift apart.
- Net interest income for the banks and State Street.
- Two more Vanguard AUM points from Vanguard's own sites (Nov 2019 and Dec 2023).
- Notebook `notebooks/02_history_findings.ipynb` walking through the analysis.
- Tests that fail if a data refresh makes a sentence in the findings untrue, and a CI step that checks charts and findings are up to date.
- Data pipeline (`data/fetch.py`) with a cached, rate-limited SEC and FRED client.
- Quarterly revenue, net income and total assets for JPMorgan, Goldman Sachs, Morgan Stanley, BlackRock and State Street, 2015 to 2025, with Q4 worked out from annual figures.
- Bank segment revenue and profit from 10-K XBRL, mapped to three business buckets.
- Quarterly AUM for BlackRock and State Street from SEC earnings releases, and Vanguard's published AUM with sources.
- 13F holdings for BlackRock, Vanguard and State Street: top 500 per quarter plus totals and coverage. Handles the 2023 value-unit change, restatements, BlackRock's subsidiary filings before 2017 and its 2024 change of SEC ID.
- FRED rates, volatility, index levels and total US public share value.
- Unit tests and offline checks on the processed data.
- MIT licence, security policy, contribution guide, Dependabot and CI.
