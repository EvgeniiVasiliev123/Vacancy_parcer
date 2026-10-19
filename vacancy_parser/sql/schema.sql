-- Схема БД. Идемпотентна: безопасно выполняется при каждом подключении.

CREATE TABLE IF NOT EXISTS vacancies (
    id             INTEGER PRIMARY KEY,          -- id вакансии на hh.ru
    name           TEXT    NOT NULL,
    role           TEXT    NOT NULL,             -- поисковый запрос, по которому вакансия найдена впервые
    area_id        INTEGER,
    area_name      TEXT,
    employer       TEXT,
    it_accredited  INTEGER,                      -- аккредитованная IT-компания (0/1)
    experience     TEXT,
    schedule       TEXT,
    employment     TEXT,
    published_at   TEXT,
    url            TEXT,
    salary_from    INTEGER,
    salary_to      INTEGER,
    currency       TEXT,
    gross          INTEGER,                      -- 1 = зарплата указана до вычета налогов
    salary_rub_net INTEGER,                      -- середина вилки в рублях "на руки"
    skills_loaded  INTEGER NOT NULL DEFAULT 0,   -- 1 = ключевые навыки уже загружены
    first_seen     TEXT    NOT NULL,
    last_seen      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS vacancy_skills (
    vacancy_id INTEGER NOT NULL REFERENCES vacancies(id) ON DELETE CASCADE,
    skill      TEXT    NOT NULL,
    PRIMARY KEY (vacancy_id, skill)
);

-- Какие вакансии были активны в каждый запуск сбора: основа для динамики рынка.
CREATE TABLE IF NOT EXISTS vacancy_seen (
    vacancy_id    INTEGER NOT NULL REFERENCES vacancies(id) ON DELETE CASCADE,
    snapshot_date TEXT    NOT NULL,
    PRIMARY KEY (vacancy_id, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_vacancies_role_area ON vacancies(role, area_name);
CREATE INDEX IF NOT EXISTS idx_skills_skill        ON vacancy_skills(skill);
CREATE INDEX IF NOT EXISTS idx_seen_date           ON vacancy_seen(snapshot_date);
