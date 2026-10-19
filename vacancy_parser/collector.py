"""Сбор вакансий: поиск -> нормализация -> запись в БД."""
from __future__ import annotations

import logging
import sqlite3
from datetime import date

from . import db
from .normalize import extract_skills, normalize_vacancy, title_matches

log = logging.getLogger(__name__)


def collect(conn: sqlite3.Connection, client, roles: list[str], areas: list[int],
            period: int = 30, per_page: int = 100, max_pages: int = 5,
            with_skills: bool = True, title_keywords: list[str] | None = None,
            snapshot_date: str | None = None) -> int:
    """Возвращает число обработанных вакансий. Навыки запрашиваются один раз на вакансию."""
    snapshot_date = snapshot_date or date.today().isoformat()
    rates = client.currency_rates()
    processed = 0
    for role in roles:
        for area in areas:
            for item in client.search(role, area, period, per_page, max_pages):
                if not title_matches(item.get("name", ""), title_keywords):
                    continue
                row = normalize_vacancy(item, role, rates)
                skills = None
                if with_skills and not db.skills_loaded(conn, row["id"]):
                    skills = extract_skills(client.vacancy(row["id"]))
                db.upsert_vacancy(conn, row, skills, snapshot_date)
                processed += 1
            conn.commit()
            log.info("Готово: %s, area=%s (всего %d)", role, area, processed)
    return processed
