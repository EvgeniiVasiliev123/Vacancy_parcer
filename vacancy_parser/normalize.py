"""Преобразование ответа API hh.ru в плоскую запись и нормализация зарплат/навыков."""
from __future__ import annotations

NET_FACTOR = 0.87  # gross -> net (НДФЛ 13%)

SKILL_ALIASES = {
    "postgres": "postgresql", "pg": "postgresql", "postgre sql": "postgresql",
    "ms sql": "sql server", "mssql": "sql server", "ms sql server": "sql server",
    "powerbi": "power bi", "power-bi": "power bi",
    "ms excel": "excel", "microsoft excel": "excel",
    "ml": "machine learning", "машинное обучение": "machine learning",
    "аналитика": "аналитика данных", "анализ данных": "аналитика данных",
    "a/b": "a/b тесты", "ab тесты": "a/b тесты", "ab-тесты": "a/b тесты",
    "git": "git", "github": "git",
}


def normalize_skill(raw: str, aliases: dict[str, str] = SKILL_ALIASES) -> str:
    s = " ".join(raw.strip().casefold().split())
    return aliases.get(s, s)


def to_rub(amount: float, currency: str | None, rates: dict[str, float]) -> float | None:
    """rates — как в /dictionaries hh.ru: единиц валюты на 1 рубль (RUR = 1)."""
    code = (currency or "RUR").upper()
    if code in ("RUR", "RUB"):
        return amount
    rate = rates.get(code)
    return amount / rate if rate else None


def salary_rub_net(salary: dict | None, rates: dict[str, float]) -> int | None:
    """Середина вилки в рублях «на руки». None, если зарплата не указана/нет курса."""
    if not salary:
        return None
    values = [v for v in (salary.get("from"), salary.get("to")) if v]
    if not values:
        return None
    rub = to_rub(sum(values) / len(values), salary.get("currency"), rates)
    if rub is None:
        return None
    if salary.get("gross"):
        rub *= NET_FACTOR
    return round(rub)


def title_matches(name: str, keywords: list[str] | None) -> bool:
    """Фильтр по названию: пусто = пропускать всё."""
    if not keywords:
        return True
    low = name.casefold()
    return any(k.casefold() in low for k in keywords)


def normalize_vacancy(item: dict, role: str, rates: dict[str, float]) -> dict:
    salary = item.get("salary") or {}
    employer = item.get("employer") or {}
    return {
        "id": int(item["id"]),
        "name": item.get("name", ""),
        "role": role,
        "area_id": int(item["area"]["id"]) if item.get("area") else None,
        "area_name": (item.get("area") or {}).get("name"),
        "employer": employer.get("name"),
        "it_accredited": int(bool(employer.get("accredited_it_employer"))),
        "experience": (item.get("experience") or {}).get("name"),
        "schedule": (item.get("schedule") or {}).get("name"),
        "employment": (item.get("employment") or {}).get("name"),
        "published_at": item.get("published_at"),
        "url": item.get("alternate_url"),
        "salary_from": salary.get("from"),
        "salary_to": salary.get("to"),
        "currency": salary.get("currency"),
        "gross": int(bool(salary.get("gross"))) if salary else None,
        "salary_rub_net": salary_rub_net(item.get("salary"), rates),
    }


def extract_skills(detail: dict) -> list[str]:
    seen, out = set(), []
    for k in detail.get("key_skills") or []:
        name = normalize_skill(k.get("name", ""))
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out
