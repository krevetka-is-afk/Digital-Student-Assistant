# Аrchitectural decision

Система строится как **модульный монолит на Python** (FastAPI), развернутый на серверах вуза. Внутри backend логически разделён на доменные модули: `users` (пользователи и роли), `projects` (карточки проектов, статусы, дедлайны), `applications` (заявки и их workflow), `cpprp` (настройки ЦППРП, ОП, шаблоны документов), `integrations` (SSO, Sheets, LMS/ЕЛК), `recs` (обёртка над ML-сервисом).

Данные хранятся в **PostgreSQL с подходом schema-per-module**: отдельные схемы `users`, `projects`, `applications`, `cpprp`, `ml`. Межмодульные связи реализуются через **суррогатные ключи** (ID), без join’ов между схемами на уровне приложения: модуль получает только свои таблицы, а нужные данные из других контекстов — через их API/сервисы.

Рекомендательная логика вынесена в отдельный **ML/LLM-сервис**, который работает с производными данными (embeddings, индексы). Связь между оперативными данными и ML обеспечивается через **очередь сообщений**: backend при изменении важных сущностей (проекты, интересы студентов) публикует события (`project_updated`, `student_interests_updated`), ML-сервис потребляет их, читает свежие данные из Postgres и обновляет свой индекс (FAISS/pgvector и т.п.). Это даёт **eventual consistency**, достаточную для домена, и поддерживает актуальность рекомендаций при регулярных обновлениях таблиц.

## 1) Общая архитектура

```mermaid
graph TD
    UI["Web-клиент (студент / заказчик / ЦППРП)"]
    API["Backend (модульный монолит, Python)"]
    DB["PostgreSQL (схемы: users, projects, applications, cpprp, ml)"]
    MQ["Очередь сообщений (Reindex Events)"]
    MLS["ML/LLM сервис рекомендаций и поиска"]
    EXT["Внешние системы (SSO edu.hse.ru, Sheets, LMS/ЕЛК)"]

    UI --> API
    API --> DB
    API --> MQ
    API --> EXT
    MQ --> MLS
    MLS --> DB
```

---

## 2) Потоки / обновление данных и рекомендации

```mermaid
graph TD
    CP["ЦППРП / заказчик обновляет таблицу проектов"]
    SHEET["Google/Yandex Sheets / XLSX"]
    IM["Backend: модуль integrations (импорт и парсинг)"]
    PRJ["DB: схема projects (проекты)"]
    MQ["Очередь Reindex (project_updated)"]
    MLS["ML/LLM сервис"]
    EMB["ML: индекс проектов (embeddings)"]
    ST["Студент в веб-клиенте"]
    API["Backend: модуль recs (рекомендации/поиск)"]

    CP --> SHEET
    SHEET --> IM
    IM --> PRJ
    PRJ --> MQ
    MQ --> MLS
    MLS --> PRJ
    MLS --> EMB

    ST --> API
    API --> MLS
    MLS --> API
```
