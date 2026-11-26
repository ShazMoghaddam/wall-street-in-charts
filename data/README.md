# Data

Everything in `processed/` is built by one script from public sources:

```bash
python data/fetch.py                  # all steps, about 2 minutes once cached
python data/fetch.py --only fred aum  # selected steps
python data/fetch.py --refresh        # re-download filing lists, facts and FRED
```

The first full run downloads about 2 GB of SEC filings into `raw/` (git-ignored), which takes a few minutes on a good connection. Later runs use that cache.

You need two secrets in a local `.env` file (see `.env.example`): `SEC_CONTACT_EMAIL`, which the SEC requires on every request, and `FRED_API_KEY`. They are never written to the cache or the outputs.

## Sources

| Source | What we take | Firms |
| --- | --- | --- |
| SEC XBRL company facts | Quarterly revenue, net income, total assets | JPMorgan, Goldman, Morgan Stanley, BlackRock, State Street |
| SEC 10-K XBRL filings | Revenue and profit by business segment (yearly) | The three banks |
| SEC 8-K earnings releases | Assets under management (AUM) each quarter | BlackRock, State Street |
| Vanguard's own figures | AUM at the dates Vanguard published it | Vanguard |
| SEC 13F-HR filings | US-listed shareholdings each quarter | BlackRock, Vanguard, State Street |
| FRED | Interest rates, volatility, index levels, total US public share value | Market context |

## Files in `processed/`

### `fundamentals_quarterly.csv`
One row per firm, metric and quarter, 2015Q1 to 2025Q4.

| Column | Meaning |
| --- | --- |
| `firm` | Firm key (see `firms.yaml`) |
| `metric` | `revenue`, `net_income` or `total_assets` |
| `quarter` | e.g. `2020Q3` |
| `value_usd` | US dollars |
| `tag` | XBRL tag used (first in the firm's priority list with a value) |
| `method` | `reported`, or how Q4 was worked out (`derived_from_full_year`, `derived_from_nine_months`) |
| `accn`, `filed` | SEC filing the figure came from |

Revenue is net of interest expense for the banks, which is how they report "net revenue".

### `aum.csv`
| Column | Meaning |
| --- | --- |
| `firm`, `as_of` | Firm and the date the figure refers to |
| `aum_trillion_usd` | Assets under management, $ trillions |
| `source`, `reference` | SEC accession number, or a link for Vanguard |

BlackRock and State Street have all 44 quarter ends. Vanguard has only the dates it published (see `manual/vanguard_aum.csv`).

### `bank_segments_annual.csv`
Yearly revenue, pre-tax income and net income by business segment, plus `bucket`:

- `markets_dealmaking`: trading and investment banking
- `wealth_asset_management`: wealth and asset management
- `banking_lending`: consumer and business banking
- `detail` (a sub-line of a segment, not added to totals) and `exclude` (corporate centre)

Each year uses the newest 10-K that reports it, so years near a reorganisation use the recast figures. The mapping lives in `manual/segment_map.csv`.

### `holdings_13f_top500.csv`
The 500 largest holdings per firm and quarter, by value. `weight` is the share of that firm's total 13F value.

### `holdings_13f_totals.csv`
One row per firm and quarter: total 13F value, number of positions, value and share covered by the top 500, and the filings used.

### `fred_daily.csv`, `fred_quarterly.csv`
Daily observations, and quarterly mean and quarter-end value. Series are listed in `firms.yaml`.

### `manifest.json`
When each step last ran and how many rows it wrote.

## Things to know

- **US-listed shares only.** 13F filings cover US-listed shares (plus some ETFs and US-listed foreign shares). They leave out bonds, cash, private assets and shares listed elsewhere, so a 13F total is much smaller than AUM.
- **13F value units.** Filings before 3 January 2023 report value in thousands of dollars; later ones in dollars. Outputs are always dollars.
- **13F amendments.** A RESTATEMENT replaces the original report and is used instead. NEW HOLDINGS amendments (a few late lines) are left out.
- **BlackRock's two SEC IDs.** BlackRock, Inc. moved to a new holding company in late 2024 (new ID 2012383). The old company, now BlackRock Finance, Inc. (ID 1364742), carries the history.
- **BlackRock before 2017.** Until Q4 2016 its main subsidiaries filed their own 13Fs, so 2015 to 2016 adds up seven filings per quarter.
- **Vanguard after 2025.** From Q1 2026 Vanguard files only 13F-NT notices, because other Vanguard companies now report its holdings. Extending past 2025 needs those filers.
- **S&P 500 on FRED** only goes back ten years (late 2016), so the Nasdaq Composite and the Fed's total market value series cover the full period.
- **Total US market value** (`BOGZ1LM883164115Q`) is the Fed's figure for US public companies' shares. It leaves out foreign companies, which 13F totals partly include.
- **Vanguard AUM** comes from Vanguard statements and press reports of Vanguard figures. Some years are not year-end figures; the date is always stated.
