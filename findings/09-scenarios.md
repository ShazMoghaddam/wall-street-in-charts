# 9. Good, middling and bad scenarios to 2030 and 2035

> **Not financial advice.** These are illustrations from a deliberately simple model, not predictions or recommendations. The future will not look like any single line here.

Each firm is linked by a simple model to the things that move it: the stock market, interest rates and market volatility. We then run 10,000 simulated futures for those drivers, built from real stretches of history since 1990 (including the 2000, 2008, 2020 and 2022 shocks), and push each one through the firm models. **Bad, middling and good are the 10th, 50th and 90th percentiles** of the results: 1 in 10 futures came out worse than 'bad', and 1 in 10 better than 'good'.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../charts/f9-profit-2035-dark.svg">
  <img src="../charts/f9-profit-2035-light.svg" alt="Profit in 2035 under each scenario · $bn: 4 series across 5 groups" width="760">
</picture>

- **JPMorgan stays far ahead.** Its 2035 profit comes out at $49.5bn (bad), $75.0bn (middling) and $109.5bn (good), against $57.0bn in 2025.
- **The range is wide, and that is the honest answer.** In the bad case, 2035 profit is below its 2025 level for JPMorgan, Goldman and State Street.
- **Goldman and Morgan Stanley have the widest ranges** relative to their size, because trading and dealmaking swing with markets. Goldman's 2035 profit: $14.7bn (bad), $28.4bn (middling) and $49.6bn (good).
- **BlackRock's AUM** reaches $33 trillion in the middling case (from $14 trillion), with a range of $21 to $49 trillion.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../charts/f9-profit-jpmorgan-dark.svg">
  <img src="../charts/f9-profit-jpmorgan-light.svg" alt="JPMorgan · profit to 2035 · $bn: 3 series over 21 points" width="372">
</picture> <picture>
  <source media="(prefers-color-scheme: dark)" srcset="../charts/f9-profit-goldman-dark.svg">
  <img src="../charts/f9-profit-goldman-light.svg" alt="Goldman · profit to 2035 · $bn: 3 series over 21 points" width="372">
</picture> <picture>
  <source media="(prefers-color-scheme: dark)" srcset="../charts/f9-profit-morgan-stanley-dark.svg">
  <img src="../charts/f9-profit-morgan-stanley-light.svg" alt="Morgan Stanley · profit to 2035 · $bn: 3 series over 21 points" width="372">
</picture> <picture>
  <source media="(prefers-color-scheme: dark)" srcset="../charts/f9-profit-blackrock-dark.svg">
  <img src="../charts/f9-profit-blackrock-light.svg" alt="BlackRock · profit to 2035 · $bn: 3 series over 21 points" width="372">
</picture> <picture>
  <source media="(prefers-color-scheme: dark)" srcset="../charts/f9-profit-state-street-dark.svg">
  <img src="../charts/f9-profit-state-street-light.svg" alt="State Street · profit to 2035 · $bn: 3 series over 21 points" width="372">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../charts/f9-aum-blackrock-dark.svg">
  <img src="../charts/f9-aum-blackrock-light.svg" alt="BlackRock · AUM to 2035 · $T: 3 series over 21 points" width="372">
</picture>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../charts/f9-aum-state-street-dark.svg">
  <img src="../charts/f9-aum-state-street-light.svg" alt="State Street · AUM to 2035 · $T: 3 series over 21 points" width="372">
</picture>

## The drivers

In the middling case the US stock market's total value grows about as fast as it did from 1990 to 2025 (about 9% a year, including new listings), reaching 2.4 times its 2025 level by 2035. The bad case is 1.2 times and the good case 4.5 times. The Fed funds rate is pulled back towards its long-run level, about 2% as estimated from 1990-2025, with real surprises along the way.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../charts/f9-market-dark.svg">
  <img src="../charts/f9-market-light.svg" alt="US stock market value in the simulations · 2025 = 100: 3 series over 11 points" width="372">
</picture>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../charts/f9-rates-dark.svg">
  <img src="../charts/f9-rates-light.svg" alt="Fed funds rate in the simulations · yearly average %: 3 series over 11 points" width="372">
</picture>

## Backtest: how close did it get?

We trained the same models on 2015 to 2020 only, then asked them about 2021 to 2025.

- **With the real market and rates fed in**, yearly revenue was off by 5% to 13% on average. Profit is harder: from 9% for JPMorgan to 38% for Goldman, whose 2021 deal boom and 2023 slump no simple model would call.
- **With everything simulated**, what actually happened landed inside the bad-to-good range 78% of the time. A well-judged 10th-to-90th range should catch about 80%.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../charts/f9-backtest-dark.svg">
  <img src="../charts/f9-backtest-light.svg" alt="Backtest 2021-2025 · bar = model (trained to 2020), mark = what happened: 8 of 10 measures at or above target. BlackRock profit $32bn, BlackRock revenue $110bn, Goldman profit $77bn, Goldman revenue $284bn, JPMorgan profit $228bn, JPMorgan revenue $761bn, Morgan Stanley profit $75bn, Morgan Stanley revenue $325bn, State Street profit $14bn, State Street revenue $72bn" width="760">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../charts/f9-backtest-error-dark.svg">
  <img src="../charts/f9-backtest-error-light.svg" alt="Backtest · average yearly error, 2021-2025 · %: 2 series across 5 groups" width="372">
</picture>

## How the models work

- **Banks:** net interest income follows interest rates and the size of the market; other revenue (trading, deals, wealth) follows the market and volatility, with quarter-of-year effects; profit margin follows rates and volatility.
- **Fund managers:** AUM follows the market plus a steady trend (new client money); revenue follows AUM and rates; profit margin follows rates and volatility.
- **Errors are simulated too.** Each model's leftover error persists from quarter to quarter, as it does in real life, so the range reflects how wrong the model has been.
- **Vanguard is left out:** its 11 published AUM figures are too few for a model.
- Everything is in `wallstreet/forecast.py`; outputs and settings (including the fixed random seed) are in `models/`.

## Limits

- Ten years is a long way. Mergers (like BlackRock's 2024 and 2025 deals), new rules or a new business line can change a firm in ways no driver captures.
- 'Good' and 'bad' describe profit and AUM, not whether an outcome is good for anyone else.
- The models are deliberately simple so that every link can be read and checked.
