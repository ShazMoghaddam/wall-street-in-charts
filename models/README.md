# Models

Forecasts to 2030 and 2035 and a backtest, built by:

```bash
python models/run.py
```

The code lives in [`wallstreet/forecast.py`](../wallstreet/forecast.py). The random seed is fixed, so every run gives the same numbers, and CI checks that the files here match a fresh run.

> **Not financial advice.** These are illustrations from a deliberately simple model, not predictions.

## How it works

1. **Drivers.** The total value of US public company shares, the Fed funds rate and the VIX, quarterly from 1990 to 2025 (`data/processed/drivers_quarterly.csv`). 10,000 futures are simulated by drawing four-quarter blocks of real history, so crashes and rate cycles keep their real shape. The rate is pulled back towards its long-run level each quarter; the VIX keeps its persistence and its link to the market.
2. **Firm models** (quarterly, 2015 to 2025), simple least-squares fits:

   | Firm type | Equation | Drivers |
   | --- | --- | --- |
   | Banks | log net interest income | Fed funds rate, log market value |
   | Banks | log other revenue | log market value, log VIX, quarter of year |
   | Banks | profit margin | Fed funds rate, log VIX |
   | Fund managers | log AUM | log market value, trend (new money) |
   | Fund managers | log revenue | log AUM, Fed funds rate |
   | Fund managers | profit margin | Fed funds rate, log VIX |

   Each model's leftover error follows an AR(1) process (it persists from one quarter to the next) and is simulated alongside the drivers.
3. **Scenarios.** Bad, middling and good are the 10th, 50th and 90th percentiles of the 10,000 outcomes, year by year.
4. **Backtest.** The same models trained on 2015 to 2020 predict 2021 to 2025, once with the real drivers fed in (testing the firm models) and once fully simulated (testing whether reality lands inside the range).

## Files

| File | What it holds |
| --- | --- |
| `forecast_annual.csv` | `firm`, `metric` (`revenue`, `net_income`, `aum`), `year`, `actual` to 2025, then `bad`, `middling`, `good` to 2035. $ billions. Revenue and profit are yearly totals; AUM is the year-end value. |
| `backtest_annual.csv` | 2021 to 2025: `actual`, `predicted_with_real_drivers`, the simulated `bad` / `middling` / `good`, `error_pct` and `inside_range`. |
| `model_terms.csv` | Every equation's coefficients, R², error persistence and number of quarters. |
| `drivers_annual.csv` | Simulated market level (average for the year, end-2025 = 100) and Fed funds rate (yearly average), at the 10th, 50th and 90th percentiles. |
| `settings.json` | Seed, number of simulations, block length, windows, the rate's long-run level and speed, and the market's 1990-2025 growth rate. |

## Limits

- Vanguard is left out: 11 published AUM figures are too few for a model.
- Ten years is long. Mergers, new rules or new business lines can change a firm in ways the drivers don't capture.
- Percentiles are taken year by year, so a single line (say, "bad") is not one consistent path through time.
