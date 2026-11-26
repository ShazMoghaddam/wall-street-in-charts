# 3. Where do the fund managers invest?

The sector mix of the US-listed shares that BlackRock, Vanguard and State Street report in their 13F filings, combined, at each year-end.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../charts/f3-sector-mix-dark.svg">
  <img src="../charts/f3-sector-mix-light.svg" alt="Big Three · sector mix of their US shares: 11 series stacked over 11 points" width="760">
</picture>

- **Technology took over.** It rose from 14% of the Big Three's holdings in 2015 to 32% in 2025, by far the largest sector.
- **Most other sectors shrank to make room,** above all health care, consumer staples, real estate and energy.
- **They didn't choose this.** It is what happened to the market itself as Apple, Microsoft, Nvidia and the rest grew (see finding 4).

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../charts/f3-sector-shift-dark.svg">
  <img src="../charts/f3-sector-shift-light.svg" alt="Change in sector share, 2015 to 2025 · points: highest Technology 18.7 pts. Technology 18.7 pts, Consumer discretionary 1.1 pts, Communication 0.9 pts, Utilities −0.7 pts, Materials −1.0 pts, Financials −1.4 pts, Industrials −2.2 pts, Energy −3.0 pts, Real estate −3.3 pts, Consumer staples −4.2 pts, Health care −4.8 pts" width="760">
</picture>

## Notes

- **US-listed shares only.** 13F filings leave out bonds, cash, private assets and shares listed outside the US.
- **Sectors** come from each company's SEC industry code (SIC), grouped into 11 sectors close to the GICS sectors index providers use. The largest holdings were checked by hand (`data/manual/sector_overrides.csv`), for example Alphabet and Meta as Communication and Visa as Financials. At least 95% of each firm's value is mapped in every quarter.
- **ETFs** held inside the filings are left out of the mix, since each is a basket of other companies.
