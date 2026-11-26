# Changelog

All notable changes to this project are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [semantic versioning](https://semver.org/).

## [Unreleased]

### Added
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
