import pytest

from vacancy_parser import analytics, db
from vacancy_parser.collector import collect
from vacancy_parser.normalize import normalize_skill, salary_rub_net, title_matches

RATES = {"RUR": 1, "USD": 0.0125}  # как в /dictionaries: единиц валюты на 1 ₽


def make_item(vid, name, salary=None, exp="От 1 года до 3 лет", schedule="Полный день", area=(1, "Москва")):
    return {"id": str(vid), "name": name, "area": {"id": str(area[0]), "name": area[1]},
            "employer": {"name": "ACME", "accredited_it_employer": True},
            "experience": {"name": exp}, "schedule": {"name": schedule},
            "employment": {"name": "Полная занятость"}, "published_at": "2026-10-01T10:00:00+0300",
            "alternate_url": f"https://hh.ru/vacancy/{vid}", "salary": salary}


class FakeClient:
    def __init__(self, items, skills):
        self.items, self.skills, self.detail_calls = items, skills, 0

    def currency_rates(self):
        return RATES

    def search(self, text, area, period, per_page=100, max_pages=5, search_field="name"):
        return iter(self.items)

    def vacancy(self, vid):
        self.detail_calls += 1
        return {"key_skills": [{"name": s} for s in self.skills[vid]]}


def test_salary_normalization():
    assert salary_rub_net(None, RATES) is None
    assert salary_rub_net({"from": None, "to": None, "currency": "RUR"}, RATES) is None
    assert salary_rub_net({"from": 100000, "to": 200000, "currency": "RUR", "gross": False}, RATES) == 150000
    assert salary_rub_net({"from": 100000, "currency": "RUR", "gross": True}, RATES) == 87000
    assert salary_rub_net({"from": 1000, "currency": "USD", "gross": False}, RATES) == 80000
    assert salary_rub_net({"from": 1000, "currency": "XXX"}, RATES) is None


def test_skill_and_title_helpers():
    assert normalize_skill("  PostgreSQL ") == "postgresql"
    assert normalize_skill("Postgres") == "postgresql"
    assert title_matches("Senior Data Analyst", ["analyst"])
    assert not title_matches("Бухгалтер", ["аналитик"])
    assert title_matches("Что угодно", None)


@pytest.fixture()
def conn():
    c = db.connect(":memory:")
    items = [
        make_item(1, "Аналитик данных", {"from": 100000, "to": 100000, "currency": "RUR", "gross": False}),
        make_item(2, "Аналитик данных (middle)", {"from": 200000, "to": 200000, "currency": "RUR", "gross": False}),
        make_item(3, "Старший аналитик", {"from": 300000, "to": 300000, "currency": "RUR", "gross": False},
                  exp="От 3 до 6 лет", schedule="Удалённая работа"),
        make_item(4, "Аналитик без зарплаты", None),
    ]
    skills = {1: ["SQL", "Python"], 2: ["SQL", "Python", "Power BI"], 3: ["SQL", "Excel"], 4: ["SQL"]}
    collect(c, FakeClient(items, skills), ["Аналитик данных"], [1], snapshot_date="2026-10-01")
    return c


def test_collect_and_upsert_idempotent(conn):
    assert conn.execute("SELECT COUNT(*) FROM vacancies").fetchone()[0] == 4
    client = FakeClient([make_item(1, "Аналитик данных")], {1: ["SQL"]})
    collect(conn, client, ["BI-аналитик"], [1], snapshot_date="2026-10-08")
    assert client.detail_calls == 0  # навыки уже загружены — повторных запросов нет
    row = conn.execute("SELECT role, first_seen, last_seen FROM vacancies WHERE id = 1").fetchone()
    assert row == ("Аналитик данных", "2026-10-01", "2026-10-08")
    assert conn.execute("SELECT COUNT(*) FROM vacancy_seen WHERE vacancy_id = 1").fetchone()[0] == 2


def test_role_salary_median(conn):
    df = analytics.run(conn, "role_salary")
    assert df.loc[0, "n"] == 3
    assert df.loc[0, "median_rub"] == 200000


def test_median_even_count(conn):
    conn.execute("UPDATE vacancies SET salary_rub_net = 400000 WHERE id = 4")
    df = analytics.run(conn, "role_salary")
    assert df.loc[0, "median_rub"] == 250000  # (200000 + 300000) / 2


def test_top_skills_share(conn):
    df = analytics.run(conn, "top_skills", limit=3)
    assert df.iloc[0]["skill"] == "sql" and df.iloc[0]["share_pct"] == 100.0
    assert df.iloc[1]["skill"] == "python" and df.iloc[1]["share_pct"] == 50.0


def test_skill_salary_and_pairs(conn):
    ss = analytics.run(conn, "skill_salary", min_n=2)
    sql_row = ss[ss["skill"] == "sql"].iloc[0]
    assert sql_row["vacancies_with_salary"] == 3 and sql_row["median_rub"] == 200000
    pairs = analytics.run(conn, "skill_pairs", min_n=2)
    assert (pairs["skill_a"].iloc[0], pairs["skill_b"].iloc[0], pairs["together"].iloc[0]) == ("python", "sql", 2)


def test_coverage_dists_and_dynamics(conn):
    cov = analytics.run(conn, "salary_coverage").iloc[0]
    assert cov["vacancies"] == 4 and cov["with_salary"] == 3 and cov["with_salary_pct"] == 75.0
    sch = analytics.run(conn, "schedule_dist")
    assert sch["share_pct"].sum() == pytest.approx(100.0)
    dyn = analytics.run(conn, "market_dynamics")
    assert dyn.loc[0, "active_vacancies"] == 4
    trend = analytics.run(conn, "skill_trend", skill="sql")
    assert trend.loc[0, "share_pct"] == 100.0
