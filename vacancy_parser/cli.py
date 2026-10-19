from __future__ import annotations

import argparse
import logging
import os

import pandas as pd

from . import analytics
from .collector import collect
from .db import DEFAULT_DB, connect
from .hh_client import HHClient

DEFAULT_ROLES = ["Аналитик данных", "BI-аналитик", "Продуктовый аналитик", "Data Scientist"]


def _cmd_collect(args: argparse.Namespace) -> int:
    user_agent = os.environ.get("HH_USER_AGENT")
    if not user_agent:
        raise SystemExit("Задайте HH_USER_AGENT, например: 'VacancyParser/1.0 (you@mail.com)'")
    client = HHClient(user_agent, token=os.environ.get("HH_TOKEN"))
    conn = connect(args.db)
    n = collect(conn, client, args.roles, args.areas, args.period, args.per_page, args.pages,
                with_skills=not args.no_skills, title_keywords=args.title_keywords)
    print(f"Обработано вакансий: {n}")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    pd.set_option("display.width", 140)
    conn = connect(args.db)
    flt = {"role": args.role, "area": args.area}
    for title, query, extra in [
        ("Покрытие зарплатами", "salary_coverage", {}),
        ("Зарплаты по ролям (₽, на руки)", "role_salary", {}),
        ("Топ навыков", "top_skills", {"limit": 15}),
        ("Навыки и зарплата", "skill_salary", {"limit": 15}),
    ]:
        print(f"\n== {title} ==")
        print(analytics.run(conn, query, **{**flt, **extra}).to_string(index=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="vacancy_parser", description=__doc__)
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("collect", help="собрать вакансии hh.ru в SQLite")
    c.add_argument("--roles", nargs="+", default=DEFAULT_ROLES)
    c.add_argument("--areas", nargs="+", type=int, default=[1, 2], help="id регионов hh.ru (1=Москва, 2=СПб)")
    c.add_argument("--period", type=int, default=30, help="за сколько дней искать")
    c.add_argument("--pages", type=int, default=5)
    c.add_argument("--per-page", type=int, default=100)
    c.add_argument("--no-skills", action="store_true", help="не запрашивать ключевые навыки")
    c.add_argument("--title-keywords", nargs="*", help="оставлять только вакансии с этими словами в названии")
    c.add_argument("--db", default=DEFAULT_DB)
    c.set_defaults(func=_cmd_collect)

    r = sub.add_parser("report", help="вывести сводку из БД")
    r.add_argument("--role")
    r.add_argument("--area", help="название города, например 'Москва'")
    r.add_argument("--db", default=DEFAULT_DB)
    r.set_defaults(func=_cmd_report)

    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s")
    return args.func(args)
