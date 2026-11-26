"""A polite, cached HTTP client for SEC EDGAR and FRED.

- SEC fair-access rules: at most 10 requests a second, and a User-Agent that
  names the tool and a contact email. We stay under 8 a second to be safe.
- Every response is cached under data/raw/, so re-runs are fast and do not
  hit the servers again. Delete a cached file (or pass refresh=True) to refetch.
- Secrets never reach the cache: the FRED key is stripped from cache paths.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit

import requests

from .config import RAW

RETRY_STATUSES = {429, 500, 502, 503, 504}
SECRET_PARAMS = {"api_key"}


class Fetcher:
    def __init__(
        self,
        user_agent: str,
        cache_dir: Path = RAW,
        min_interval: float = 0.125,
        max_retries: int = 5,
        timeout: float = 60.0,
    ) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"})
        self.cache_dir = cache_dir
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.timeout = timeout
        self._last_request = 0.0

    def cache_path(self, url: str) -> Path:
        return self.cache_dir / cache_key(url)

    def get_bytes(self, url: str, refresh: bool = False) -> bytes:
        path = self.cache_path(url)
        if path.exists() and not refresh:
            return path.read_bytes()
        content = self._download(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".part")
        tmp.write_bytes(content)
        tmp.replace(path)
        return content

    def get_json(self, url: str, refresh: bool = False) -> dict:
        return json.loads(self.get_bytes(url, refresh=refresh))

    def get_text(self, url: str, refresh: bool = False) -> str:
        return self.get_bytes(url, refresh=refresh).decode("utf-8", errors="replace")

    def _download(self, url: str) -> bytes:
        for attempt in range(self.max_retries + 1):
            wait = self.min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.monotonic()
            try:
                resp = self.session.get(url, timeout=self.timeout)
            except requests.RequestException:
                if attempt == self.max_retries:
                    raise
                time.sleep(2**attempt)
                continue
            if resp.status_code == 200:
                if b"Undeclared Automated Tool" in resp.content[:2000]:
                    raise RuntimeError("SEC rejected the request: check SEC_CONTACT_EMAIL.")
                return resp.content
            if resp.status_code in RETRY_STATUSES and attempt < self.max_retries:
                time.sleep(min(60, 2 ** (attempt + 1)))
                continue
            resp.raise_for_status()
        raise RuntimeError(f"Failed to fetch {redact(url)}")


def redact(url: str) -> str:
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k not in SECRET_PARAMS]
    return parts._replace(query=urlencode(query)).geturl()


def cache_key(url: str) -> str:
    """Readable cache path: host/path, with a short hash when there is a query."""
    clean = redact(url)
    parts = urlsplit(clean)
    path = parts.path.lstrip("/") or "index"
    if parts.query:
        digest = hashlib.sha256(parts.query.encode()).hexdigest()[:12]
        path = f"{path}__{digest}"
    return f"{parts.netloc}/{path}"
