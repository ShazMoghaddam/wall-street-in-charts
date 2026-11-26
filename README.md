# Wall Street in Charts

[![Check](https://github.com/ShazMoghaddam/wall-street-in-charts/actions/workflows/ci.yml/badge.svg)](https://github.com/ShazMoghaddam/wall-street-in-charts/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)

Six Wall Street giants, told through their SEC filings from 2015 to 2025, with forecasts to 2030 and 2035.

- **Banks:** JPMorgan Chase, Goldman Sachs, Morgan Stanley
- **Fund managers:** BlackRock, Vanguard, State Street

> **Status:** stage 1 of 5. The data pipeline is built. Findings, holdings analysis, forecasts and the report site come next.

## The questions

1. Who grew biggest: revenue, profit and assets?
2. Where do the banks make their money: trading and dealmaking, wealth management, or lending?
3. Where do the fund managers invest, sector by sector?
4. Do they choose sectors, or just follow the market?
5. Energy then and now: oil, gas and clean energy holdings since 2015
6. How much of the US stock market do BlackRock, Vanguard and State Street hold between them?
7. How did profits move when interest rates rose in 2022?
8. Shocks: 2020, the 2022 rate rises, and the 2023 bank failures
9. Good, middling and bad scenarios to 2030 and 2035

## Data

All from public sources: SEC filings (company results, segment figures, earnings releases and 13F holdings) and FRED (rates and market levels). Vanguard is private, so it is judged on assets under management from its own published figures and on its 13F holdings.

Holdings cover **US-listed shares only**, as reported in 13F filings.

See [`data/README.md`](data/README.md) for every file, column and caveat.

## Run it

```bash
git clone https://github.com/ShazMoghaddam/wall-street-in-charts.git
cd wall-street-in-charts
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # add your SEC contact email and FRED API key
python data/fetch.py
pytest
```

## Layout

```
data/        fetch script, firm settings, hand-made tables, processed CSVs
wallstreet/  pipeline code (SEC, 13F, segments, AUM, FRED)
tests/       unit tests and checks on the processed data
```

`charts/`, `findings/`, `notebooks/` and `models/` arrive in later stages.

## Not financial advice

This is an independent data project. Nothing here is investment advice or a recommendation to buy or sell anything.

## Licence

[MIT](LICENSE)

---

Created by **Shaz Moghaddam** · London  
[Website](https://shazmoghaddam.github.io/) · [LinkedIn](https://www.linkedin.com/in/shazmoghaddam/)
