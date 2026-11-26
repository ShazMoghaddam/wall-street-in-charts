"""Paths, firm settings and secrets.

Secrets (the SEC contact email and the FRED API key) are read from environment
variables only. For local runs, put them in a `.env` file at the repo root
(it is git-ignored); see `.env.example`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
MANUAL = DATA / "manual"
FIRMS_FILE = DATA / "firms.yaml"


class MissingSecretError(RuntimeError):
    """Raised when a required environment variable is not set."""


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Load KEY=value lines from a local .env file without overriding the shell."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def require_env(name: str, help_text: str) -> str:
    load_dotenv()
    value = os.environ.get(name, "").strip()
    if not value:
        raise MissingSecretError(f"{name} is not set. {help_text}")
    return value


def sec_user_agent() -> str:
    """The SEC asks every automated request to name the tool and a contact email."""
    email = require_env(
        "SEC_CONTACT_EMAIL",
        "The SEC needs a contact email on every request. Add it to .env.",
    )
    return f"wall-street-in-charts {email}"


def fred_api_key() -> str:
    return require_env(
        "FRED_API_KEY",
        "Get a free key at https://fredaccount.stlouisfed.org/apikeys and add it to .env.",
    )


@dataclass(frozen=True)
class Firm:
    key: str
    name: str
    short: str
    ticker: str | None
    group: str
    cik: tuple[int, ...]
    thirteenf_cik: tuple[int, ...]
    revenue_tags: tuple[str, ...]
    thirteenf_parts_cik: tuple[int, ...] = ()
    thirteenf_parts_until: date | None = None

    @property
    def files_results(self) -> bool:
        return bool(self.cik)


@dataclass(frozen=True)
class Settings:
    firms: dict[str, Firm]
    start: date
    end: date
    fred_series: dict[str, str]


def load_settings(path: Path = FIRMS_FILE) -> Settings:
    raw = yaml.safe_load(path.read_text())
    firms = {
        key: Firm(
            key=key,
            name=f["name"],
            short=f["short"],
            ticker=f.get("ticker"),
            group=f["group"],
            cik=tuple(f.get("cik") or ()),
            thirteenf_cik=tuple(f.get("thirteenf_cik") or ()),
            revenue_tags=tuple(f.get("revenue_tags") or ()),
            thirteenf_parts_cik=tuple(f.get("thirteenf_parts_cik") or ()),
            thirteenf_parts_until=(
                _as_date(f["thirteenf_parts_until"]) if f.get("thirteenf_parts_until") else None
            ),
        )
        for key, f in raw["firms"].items()
    }
    period = raw["period"]
    return Settings(
        firms=firms,
        start=_as_date(period["start"]),
        end=_as_date(period["end"]),
        fred_series=dict(raw["fred_series"]),
    )


def _as_date(value: str | date) -> date:
    return value if isinstance(value, date) else date.fromisoformat(value)
