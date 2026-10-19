-- Аналитические запросы. Формат: "-- name: <имя>" перед каждым запросом.
-- Именованные параметры: :role, :area (NULL = без фильтра), :limit, :min_n, :skill.
-- SQLite не имеет MEDIAN, поэтому медиана считается через оконные функции.

-- name: salary_coverage
-- Доля вакансий с указанной зарплатой (важно для оценки смещения выборки).
SELECT v.role,
       COUNT(*)                                             AS vacancies,
       SUM(v.salary_rub_net IS NOT NULL)                    AS with_salary,
       ROUND(100.0 * SUM(v.salary_rub_net IS NOT NULL) / COUNT(*), 1) AS with_salary_pct
FROM vacancies v
WHERE (:area IS NULL OR v.area_name = :area)
GROUP BY v.role
ORDER BY vacancies DESC;

-- name: role_salary
-- Медиана, квартили и размер выборки по ролям (рубли, на руки).
WITH ranked AS (
    SELECT v.role, v.salary_rub_net AS s,
           ROW_NUMBER() OVER (PARTITION BY v.role ORDER BY v.salary_rub_net) AS rn,
           COUNT(*)     OVER (PARTITION BY v.role)                           AS cnt
    FROM vacancies v
    WHERE v.salary_rub_net IS NOT NULL
      AND (:area IS NULL OR v.area_name = :area)
)
SELECT role,
       MAX(cnt)                                                         AS n,
       ROUND(AVG(CASE WHEN rn IN ((cnt + 1) / 2, (cnt + 2) / 2) THEN s END)) AS median_rub,
       MAX(CASE WHEN rn = MAX(1, CAST(cnt * 0.25 AS INT)) THEN s END)   AS p25_rub,
       MAX(CASE WHEN rn = MAX(1, CAST(cnt * 0.75 AS INT)) THEN s END)   AS p75_rub
FROM ranked
GROUP BY role
ORDER BY median_rub DESC;

-- name: experience_salary
-- Медиана зарплаты по требуемому опыту.
WITH ranked AS (
    SELECT v.experience, v.salary_rub_net AS s,
           ROW_NUMBER() OVER (PARTITION BY v.experience ORDER BY v.salary_rub_net) AS rn,
           COUNT(*)     OVER (PARTITION BY v.experience)                           AS cnt
    FROM vacancies v
    WHERE v.salary_rub_net IS NOT NULL
      AND (:role IS NULL OR v.role = :role)
      AND (:area IS NULL OR v.area_name = :area)
)
SELECT experience, MAX(cnt) AS n,
       ROUND(AVG(CASE WHEN rn IN ((cnt + 1) / 2, (cnt + 2) / 2) THEN s END)) AS median_rub
FROM ranked
GROUP BY experience
HAVING n >= :min_n
ORDER BY median_rub;

-- name: top_skills
-- Топ навыков и доля вакансий (среди вакансий, у которых навыки загружены).
WITH base AS (
    SELECT v.id
    FROM vacancies v
    WHERE EXISTS (SELECT 1 FROM vacancy_skills s WHERE s.vacancy_id = v.id)
      AND (:role IS NULL OR v.role = :role)
      AND (:area IS NULL OR v.area_name = :area)
)
SELECT s.skill,
       COUNT(*)                                              AS vacancies,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM base), 1) AS share_pct,
       RANK() OVER (ORDER BY COUNT(*) DESC)                  AS rnk
FROM vacancy_skills s
JOIN base b ON b.id = s.vacancy_id
GROUP BY s.skill
ORDER BY vacancies DESC, s.skill
LIMIT :limit;

-- name: skill_salary
-- Медиана зарплаты по навыкам (только навыки с >= :min_n вакансий с зарплатой).
WITH ranked AS (
    SELECT s.skill, v.salary_rub_net AS sal,
           ROW_NUMBER() OVER (PARTITION BY s.skill ORDER BY v.salary_rub_net) AS rn,
           COUNT(*)     OVER (PARTITION BY s.skill)                           AS cnt
    FROM vacancy_skills s
    JOIN vacancies v ON v.id = s.vacancy_id
    WHERE v.salary_rub_net IS NOT NULL
      AND (:role IS NULL OR v.role = :role)
      AND (:area IS NULL OR v.area_name = :area)
)
SELECT skill, MAX(cnt) AS vacancies_with_salary,
       ROUND(AVG(CASE WHEN rn IN ((cnt + 1) / 2, (cnt + 2) / 2) THEN sal END)) AS median_rub
FROM ranked
GROUP BY skill
HAVING vacancies_with_salary >= :min_n
ORDER BY median_rub DESC
LIMIT :limit;

-- name: skill_pairs
-- Какие навыки чаще всего требуют вместе (самосоединение).
SELECT a.skill AS skill_a, b.skill AS skill_b, COUNT(*) AS together
FROM vacancy_skills a
JOIN vacancy_skills b ON b.vacancy_id = a.vacancy_id AND a.skill < b.skill
JOIN vacancies v      ON v.id = a.vacancy_id
WHERE (:role IS NULL OR v.role = :role)
  AND (:area IS NULL OR v.area_name = :area)
GROUP BY a.skill, b.skill
HAVING together >= :min_n
ORDER BY together DESC
LIMIT :limit;

-- name: experience_dist
-- Распределение требуемого опыта по ролям (доля внутри роли, оконная сумма).
SELECT v.role, v.experience, COUNT(*) AS vacancies,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY v.role), 1) AS share_pct
FROM vacancies v
WHERE (:area IS NULL OR v.area_name = :area)
GROUP BY v.role, v.experience
ORDER BY v.role, vacancies DESC;

-- name: schedule_dist
-- Распределение графиков работы (в т.ч. удалёнка) по ролям.
SELECT v.role, v.schedule, COUNT(*) AS vacancies,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY v.role), 1) AS share_pct
FROM vacancies v
WHERE (:area IS NULL OR v.area_name = :area)
GROUP BY v.role, v.schedule
ORDER BY v.role, vacancies DESC;

-- name: market_dynamics
-- Число активных вакансий по запускам сбора.
SELECT s.snapshot_date, v.role, COUNT(*) AS active_vacancies
FROM vacancy_seen s
JOIN vacancies v ON v.id = s.vacancy_id
WHERE (:role IS NULL OR v.role = :role)
  AND (:area IS NULL OR v.area_name = :area)
GROUP BY s.snapshot_date, v.role
ORDER BY s.snapshot_date, v.role;

-- name: skill_trend
-- Доля вакансий с навыком :skill по запускам сбора.
SELECT s.snapshot_date,
       COUNT(*) AS active_vacancies,
       SUM(EXISTS (SELECT 1 FROM vacancy_skills k
                   WHERE k.vacancy_id = v.id AND k.skill = :skill)) AS with_skill,
       ROUND(100.0 * SUM(EXISTS (SELECT 1 FROM vacancy_skills k
                   WHERE k.vacancy_id = v.id AND k.skill = :skill)) / COUNT(*), 1) AS share_pct
FROM vacancy_seen s
JOIN vacancies v ON v.id = s.vacancy_id
WHERE (:role IS NULL OR v.role = :role)
  AND (:area IS NULL OR v.area_name = :area)
GROUP BY s.snapshot_date
ORDER BY s.snapshot_date;
