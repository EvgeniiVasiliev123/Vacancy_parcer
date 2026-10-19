"""Streamlit-дашборд. Запуск: streamlit run dashboard.py"""
import plotly.express as px
import streamlit as st

from vacancy_parser import analytics
from vacancy_parser.db import DEFAULT_DB, connect

st.set_page_config(page_title="Рынок вакансий hh.ru", layout="wide")
st.title("Рынок вакансий аналитиков данных (hh.ru)")

db_path = st.sidebar.text_input("Путь к БД", DEFAULT_DB)
conn = connect(db_path)

roles = ["Все"] + analytics.run(conn, "salary_coverage")["role"].tolist()
cities = ["Все"] + [r[0] for r in conn.execute(
    "SELECT DISTINCT area_name FROM vacancies WHERE area_name IS NOT NULL ORDER BY 1")]
role = st.sidebar.selectbox("Роль", roles)
city = st.sidebar.selectbox("Город", cities)
min_n = st.sidebar.slider("Мин. вакансий с зарплатой для навыка", 3, 30, 5)
flt = {"role": None if role == "Все" else role, "area": None if city == "Все" else city}

total = conn.execute("SELECT COUNT(*) FROM vacancies").fetchone()[0]
if total == 0:
    st.warning("БД пуста. Сначала выполните: python -m vacancy_parser collect")
    st.stop()

cov = analytics.run(conn, "salary_coverage", area=flt["area"])
c1, c2, c3 = st.columns(3)
c1.metric("Вакансий в БД", int(cov["vacancies"].sum()))
c2.metric("С указанной зарплатой", f'{cov["with_salary"].sum() / cov["vacancies"].sum():.0%}')
c3.metric("Ролей", len(cov))
st.caption("Зарплата указана не во всех вакансиях, поэтому выводы о зарплатах относятся только к ним.")

left, right = st.columns(2)
with left:
    st.subheader("Зарплаты по ролям (медиана, ₽ на руки)")
    sal = analytics.run(conn, "role_salary", area=flt["area"])
    if len(sal):
        st.plotly_chart(px.bar(sal, x="role", y="median_rub", hover_data=["n", "p25_rub", "p75_rub"]),
                        use_container_width=True)
with right:
    st.subheader("Топ навыков (% вакансий)")
    top = analytics.run(conn, "top_skills", limit=15, **flt)
    if len(top):
        st.plotly_chart(px.bar(top.sort_values("share_pct"), x="share_pct", y="skill", orientation="h"),
                        use_container_width=True)

st.subheader("Спрос на навык и зарплата")
ss = analytics.run(conn, "skill_salary", limit=40, min_n=min_n, **flt)
tp = analytics.run(conn, "top_skills", limit=200, **flt)
merged = ss.merge(tp, on="skill")
if len(merged):
    st.plotly_chart(px.scatter(merged, x="share_pct", y="median_rub", text="skill", size="vacancies_with_salary",
                               labels={"share_pct": "Доля вакансий, %", "median_rub": "Медиана зарплаты, ₽"}),
                    use_container_width=True)
else:
    st.info("Недостаточно данных: уменьшите порог или соберите больше вакансий.")

a, b = st.columns(2)
with a:
    st.subheader("Требуемый опыт")
    exp = analytics.run(conn, "experience_dist", area=flt["area"])
    if flt["role"]:
        exp = exp[exp["role"] == flt["role"]]
    st.plotly_chart(px.bar(exp, x="experience", y="share_pct", color="role", barmode="group"),
                    use_container_width=True)
with b:
    st.subheader("Графики работы")
    sch = analytics.run(conn, "schedule_dist", area=flt["area"])
    if flt["role"]:
        sch = sch[sch["role"] == flt["role"]]
    st.plotly_chart(px.bar(sch, x="schedule", y="share_pct", color="role", barmode="group"),
                    use_container_width=True)

st.subheader("Часто требуемые вместе навыки")
st.dataframe(analytics.run(conn, "skill_pairs", limit=20, min_n=min_n, **flt), use_container_width=True)

dyn = analytics.run(conn, "market_dynamics", **flt)
if dyn["snapshot_date"].nunique() > 1:
    st.subheader("Динамика числа активных вакансий")
    st.plotly_chart(px.line(dyn, x="snapshot_date", y="active_vacancies", color="role", markers=True),
                    use_container_width=True)
