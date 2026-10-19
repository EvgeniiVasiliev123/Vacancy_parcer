"""Клиент API hh.ru: ретраи с бэкоффом, пауза между запросами, без прокси."""
from __future__ import annotations

import logging
import time
from typing import Iterator

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API = "https://api.hh.ru"
MAX_RESULTS = 2000  # ограничение API: page * per_page <= 2000
log = logging.getLogger(__name__)


class HHClient:
    def __init__(self, user_agent: str, token: str | None = None,
                 delay: float = 0.3, timeout: float = 15):
        self.delay, self.timeout = delay, timeout
        self.session = requests.Session()
        retry = Retry(total=5, backoff_factor=1.0, status_forcelist=(429, 500, 502, 503, 504),
                      allowed_methods=("GET",), respect_retry_after_header=True)
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.headers.update({"User-Agent": user_agent, "HH-User-Agent": user_agent})
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def _get(self, path: str, params: dict | None = None) -> dict:
        resp = self.session.get(f"{API}{path}", params=params, timeout=self.timeout)
        resp.raise_for_status()
        time.sleep(self.delay)
        return resp.json()

    def search(self, text: str, area: int, period: int, per_page: int = 100,
               max_pages: int = 5, search_field: str = "name") -> Iterator[dict]:
        per_page = min(per_page, 100)
        max_pages = min(max_pages, MAX_RESULTS // per_page)
        for page in range(max_pages):
            data = self._get("/vacancies", {
                "text": text, "area": area, "period": period, "per_page": per_page,
                "page": page, "search_field": search_field,
            })
            log.info("%s / area=%s: страница %d/%s", text, area, page + 1, data.get("pages"))
            yield from data.get("items", [])
            if page + 1 >= data.get("pages", 0):
                break

    def vacancy(self, vacancy_id: int) -> dict:
        return self._get(f"/vacancies/{vacancy_id}")

    def currency_rates(self) -> dict[str, float]:
        data = self._get("/dictionaries")
        return {c["code"].upper(): c["rate"] for c in data.get("currency", [])}
