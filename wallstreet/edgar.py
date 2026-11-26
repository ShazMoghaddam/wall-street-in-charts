"""Filing lists and filing folders on SEC EDGAR."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .http import Fetcher

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
SUBMISSIONS_PAGE_URL = "https://data.sec.gov/submissions/{name}"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accn_nodash}/"


@dataclass(frozen=True)
class Filing:
    cik: int
    form: str
    accn: str
    filed: date
    report_date: date | None
    primary_document: str
    items: str

    @property
    def folder_url(self) -> str:
        return ARCHIVE_URL.format(cik=self.cik, accn_nodash=self.accn.replace("-", ""))

    @property
    def index_url(self) -> str:
        return self.folder_url + "index.json"


def _rows(block: dict, cik: int) -> list[Filing]:
    out = []
    n = len(block.get("accessionNumber", []))
    for i in range(n):
        report = block["reportDate"][i]
        out.append(
            Filing(
                cik=cik,
                form=block["form"][i],
                accn=block["accessionNumber"][i],
                filed=date.fromisoformat(block["filingDate"][i]),
                report_date=date.fromisoformat(report) if report else None,
                primary_document=block["primaryDocument"][i],
                items=block.get("items", [""] * n)[i] or "",
            )
        )
    return out


def list_filings(
    fetcher: Fetcher, cik: int, forms: set[str], since: date | None = None
) -> list[Filing]:
    """Every filing of the given forms, newest first, following older pages as needed."""
    doc = fetcher.get_json(SUBMISSIONS_URL.format(cik=cik))
    filings = _rows(doc["filings"]["recent"], cik)
    for page in doc["filings"].get("files", []):
        if since and date.fromisoformat(page["filingTo"]) < since:
            continue
        filings += _rows(fetcher.get_json(SUBMISSIONS_PAGE_URL.format(name=page["name"])), cik)
    wanted = [f for f in filings if f.form in forms and (since is None or f.filed >= since)]
    return sorted(wanted, key=lambda f: (f.filed, f.accn), reverse=True)


def folder_files(fetcher: Fetcher, filing: Filing) -> list[dict]:
    """Name and size of every file in a filing folder."""
    items = fetcher.get_json(filing.index_url)["directory"]["item"]
    return [{"name": i["name"], "size": int(i.get("size") or 0)} for i in items]
