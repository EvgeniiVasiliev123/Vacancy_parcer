"""Работа с SQLite: подключение, схема, upsert, загрузка именованных запросов."""
from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB = "data/vacancies.db"
_SQL_DIR = Path(__file__).with_name("sql")

_VACANCY_COLS = (
    "id", "name", "role", "area_id", "area_name", "employer", "it_accredited",
    "experience", "schedule", "employment", "published_at", "url",
    "salary_from", "salary_to", "currency", "gross", "salary_rub_net",
)


def connect(path: str = DEFAULT_DB) -> sqlite3.Connection:
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript((_SQL_DIR / "schema.sql").read_text(encoding="utf-8"))
    return conn


def load_queries() -> dict[str, str]:
    """Разбирает queries.sql на словарь {имя: SQL}."""
    queries: dict[str, list[str]] = {}
    current = None
    for line in (_SQL_DIR / "queries.sql").read_text(encoding="utf-8").splitlines():
        if line.startswith("-- name:"):
            current = line.split(":", 1)[1].strip()
            queries[current] = []
        elif current is not None:
            queries[current].append(line)
    return {name: "\n".join(body).strip() for name, body in queries.items()}


def skills_loaded(conn: sqlite3.Connection, vacancy_id: int) -> bool:
    row = conn.execute("SELECT skills_loaded FROM vacancies WHERE id = ?", (vacancy_id,)).fetchone()
    return bool(row and row[0])


def upsert_vacancy(conn: sqlite3.Connection, row: dict, skills: list[str] | None,
                   snapshot_date: str) -> None:
    """Добавляет/обновляет вакансию. Роль и first_seen при обновлении не меняются."""
    params = {c: row.get(c) for c in _VACANCY_COLS}
    params["snapshot_date"] = snapshot_date
    placeholders = ", ".join(f":{c}" for c in _VACANCY_COLS)
    updatable = [c for c in _VACANCY_COLS if c not in ("id", "role")]
    update_sql = ", ".join(f"{c} = excluded.{c}" for c in updatable)
    conn.execute(
        f"""INSERT INTO vacancies ({", ".join(_VACANCY_COLS)}, first_seen, last_seen)
            VALUES ({placeholders}, :snapshot_date, :snapshot_date)
            ON CONFLICT(id) DO UPDATE SET {update_sql}, last_seen = excluded.last_seen""",
        params,
    )
    conn.execute("INSERT OR IGNORE INTO vacancy_seen (vacancy_id, snapshot_date) VALUES (?, ?)",
                 (row["id"], snapshot_date))
    if skills is not None:
        conn.execute("DELETE FROM vacancy_skills WHERE vacancy_id = ?", (row["id"],))
        conn.executemany("INSERT OR IGNORE INTO vacancy_skills (vacancy_id, skill) VALUES (?, ?)",
                         [(row["id"], s) for s in skills])
        conn.execute("UPDATE vacancies SET skills_loaded = 1 WHERE id = ?", (row["id"],))
