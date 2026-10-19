"""Тонкая обёртка: выполняет именованные SQL-запросы и возвращает DataFrame."""
from __future__ import annotations

import sqlite3

import pandas as pd

from .db import load_queries

DEFAULTS = {"role": None, "area": None, "limit": 20, "min_n": 5, "skill": None}


def run(conn: sqlite3.Connection, name: str, **params) -> pd.DataFrame:
    sql = load_queries()[name]
    merged = {**DEFAULTS, **params}
    used = {k: v for k, v in merged.items() if f":{k}" in sql}
    return pd.read_sql_query(sql, conn, params=used)
