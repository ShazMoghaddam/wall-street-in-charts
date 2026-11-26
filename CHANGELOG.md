# Changelog

All notable changes to this project are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [semantic versioning](https://semver.org/).

## [Unreleased]

### Added
- Data pipeline (`data/fetch.py`) with a cached, rate-limited SEC and FRED client.
- Quarterly revenue, net income and total assets for JPMorgan, Goldman Sachs, Morgan Stanley, BlackRock and State Street, 2015 to 2025, with Q4 worked out from annual figures.
- Bank segment revenue and profit from 10-K XBRL, mapped to three business buckets.
- Quarterly AUM for BlackRock and State Street from SEC earnings releases, and Vanguard's published AUM with sources.
- 13F holdings for BlackRock, Vanguard and State Street: top 500 per quarter plus totals and coverage. Handles the 2023 value-unit change, restatements, BlackRock's subsidiary filings before 2017 and its 2024 change of SEC ID.
- FRED rates, volatility, index levels and total US public share value.
- Unit tests and offline checks on the processed data.
- MIT licence, security policy, contribution guide, Dependabot and CI.
