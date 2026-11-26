"""Map 13F holdings (by CUSIP) to 11 sectors.

13F filings give a CUSIP and the issuer's name, but no sector. We:

1. match the issuer name to an SEC company (CIK), using the SEC's list of
   every company name it has ever had (cik-lookup-data.txt) and the list of
   listed companies (company_tickers.json),
2. read that company's SIC industry code from its SEC filing record,
3. group SIC codes into 11 sectors close to the GICS sectors index providers
   use (data/manual/sic_sectors.csv),
4. apply hand checks for the largest holdings (data/manual/sector_overrides.csv),
   for example Alphabet and Meta as Communication rather than "computer
   services", and Amazon as Consumer discretionary rather than retail.

ETFs and other funds are flagged and kept out of the sector mix.
"""

from __future__ import annotations

import re
from functools import cache

import pandas as pd

from .config import MANUAL
from .http import Fetcher

SECTORS = [
    "Technology",
    "Communication",
    "Consumer discretionary",
    "Consumer staples",
    "Health care",
    "Financials",
    "Industrials",
    "Energy",
    "Materials",
    "Utilities",
    "Real estate",
]
FUNDS = "Funds (ETFs)"
UNMAPPED = "Not mapped"

CIK_LOOKUP_URL = "https://www.sec.gov/Archives/edgar/cik-lookup-data.txt"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"

# Words that don't help tell companies apart.
DROP = {
    "INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED",
    "PLC", "LLC", "LP", "L P", "SA", "NV", "AG", "SE", "THE", "DEL", "NEW", "HLDGS",
    "HOLDINGS", "HOLDING", "GROUP", "GRP", "COM", "CL", "CLASS", "A", "B", "C", "SHS",
    "ORD", "ADR", "SPONSORED", "SPON", "REIT", "TR", "TRUST",
    # US state suffixes in SEC names, as in "QUALCOMM INC/DE"
    "DE", "MD", "NJ", "PA", "NY", "CA", "TX", "OH", "MN", "FL", "VA", "WA", "MA",
    "WI", "IN", "IL", "GA", "CT", "MI", "NC", "TN", "AZ", "OR", "MO", "KY",
}  # fmt: skip

ETF_WORDS = re.compile(
    r"\b(ETF|ETN|ISHARES|SPDR|PROSHARES|INVESCO QQQ|SELECT SECTOR|DIREXION|WISDOMTREE|"
    r"GLOBAL X|VANECK|VAN ECK|SCHWAB STRATEGIC|INDEX FD|INDEX FDS|VANGUARD|FIRST TR|"
    r"ISHARES TR|ETF TR|UNIT SER|S&P 500 ETF|NASDAQ 100 ETF)\b"
)


def normalise(name: str) -> str:
    text = re.sub(r"[^A-Z0-9 ]", " ", str(name).upper().replace("&", " AND "))
    words = [w for w in text.split() if w not in DROP]
    return " ".join(words)


def is_fund(issuer: str, title_of_class: str = "") -> bool:
    text = f"{issuer} {title_of_class}".upper()
    return bool(ETF_WORDS.search(text))


@cache
def sic_sector_table() -> pd.DataFrame:
    return pd.read_csv(MANUAL / "sic_sectors.csv")


def sic_to_sector(sic: int | None) -> str:
    if sic is None or pd.isna(sic):
        return UNMAPPED
    table = sic_sector_table()
    hit = table[(table["sic_from"] <= sic) & (table["sic_to"] >= sic)]
    if hit.empty:
        return UNMAPPED
    # The narrowest range wins, so 2834 (pharma) beats 2800-2899 (chemicals).
    hit = hit.assign(width=hit["sic_to"] - hit["sic_from"]).sort_values("width")
    return str(hit.iloc[0]["sector"])


def name_index(fetcher: Fetcher) -> dict[str, list[int]]:
    """Normalised company name -> CIKs, listed companies first."""
    index: dict[str, list[int]] = {}
    for row in fetcher.get_json(TICKERS_URL).values():
        index.setdefault(normalise(row["title"]), []).append(int(row["cik_str"]))
    listed = {c for cs in index.values() for c in cs}
    for line in fetcher.get_text(CIK_LOOKUP_URL).splitlines():
        parts = line.rsplit(":", 2)
        if len(parts) < 3 or not parts[1].isdigit():
            continue
        key = normalise(parts[0])
        if not key:
            continue
        ciks = index.setdefault(key, [])
        cik = int(parts[1])
        if cik not in ciks:
            ciks.append(cik)
    # Listed companies first within each name.
    for ciks in index.values():
        ciks.sort(key=lambda c: (c not in listed, c))
    return index


def company_sic(fetcher: Fetcher, cik: int) -> tuple[int | None, str]:
    try:
        doc = fetcher.get_json(SUBMISSIONS_URL.format(cik=cik))
    except Exception:  # noqa: BLE001 - a missing record just means no SIC
        return None, ""
    sic = doc.get("sic")
    return (int(sic) if sic not in (None, "") else None), doc.get("name", "")


def map_cusips(fetcher: Fetcher, universe: pd.DataFrame) -> pd.DataFrame:
    """Sector for each CUSIP in `universe` (columns cusip, issuer, title_of_class).

    `universe` may hold several issuer spellings per CUSIP; each is tried.
    """
    overrides = pd.read_csv(MANUAL / "sector_overrides.csv", dtype=str)
    by_cusip = dict(zip(overrides["cusip"], overrides["sector"], strict=True))
    index = name_index(fetcher)
    rows = []
    for cusip, group in universe.groupby("cusip"):
        names = list(dict.fromkeys(group["issuer"]))
        title = str(group["title_of_class"].iloc[0])
        row = {"cusip": cusip, "issuer": names[0], "cik": None, "sic": None, "sec_name": ""}
        if not any(is_fund(n, title) for n in names):
            for name in names:
                for cik in index.get(normalise(name), [])[:3]:
                    sic, sec_name = company_sic(fetcher, cik)
                    if sic is not None:
                        row.update(cik=cik, sic=sic, sec_name=sec_name)
                        break
                if row["sic"] is not None:
                    break
        if cusip in by_cusip:
            row.update(sector=by_cusip[cusip], method="hand-checked")
        elif any(is_fund(n, title) for n in names) or row["sic"] == 6726:
            row.update(sector=FUNDS, method="fund name")
        elif row["sic"] is not None:
            row.update(sector=sic_to_sector(row["sic"]), method="SIC code")
        else:
            row.update(sector=UNMAPPED, method="no match")
        rows.append(row)
    return pd.DataFrame(rows)


@cache
def clean_energy_patterns() -> list[tuple[str, str]]:
    df = pd.read_csv(MANUAL / "clean_energy.csv")
    out = []
    for row in df.itertuples():
        for pattern in str(row.match).split("|"):
            out.append((normalise(pattern), row.name))
    return out


def clean_energy_name(issuer: str) -> str | None:
    """The clean energy company an issuer name belongs to, if any."""
    key = normalise(issuer)
    for pattern, name in clean_energy_patterns():
        if key == pattern or key.startswith(pattern + " "):
            return name
    return None
