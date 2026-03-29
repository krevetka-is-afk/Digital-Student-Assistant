# Аrchitectural decision

Текущая реализация строится как **модульный монолит на Python** (`src/web`, Django + DRF), развернутый вместе с отдельными `ml` и `graph` сервисами. Внутри backend логически разделён на доменные модули: `users`, `projects`, `applications`, `account`, `imports`, `outbox`, `recs`.

Операционные данные обслуживает Django ORM: в dev/test используется SQLite, production-target остается PostgreSQL. Границы модулей задаются кодом и API-контрактами, а не отдельными БД-схемами. Канонические runtime contracts зафиксированы в generated OpenAPI и в `docs/architecture/contracts/*`.

Рекомендательная логика вынесена в отдельный **ML-сервис**, а связи между студентами, научными руководителями, тегами и заявками строятся в отдельном **graph projector** сервисе. Связь между web backend и downstream сервисами обеспечивается через **outbox feed** (`/api/v1/outbox/events/`): backend публикует события `project.changed`, `application.changed`, `user_profile.changed`, `deadline.changed`, `import.completed`, `recs.reindex_requested`. Это даёт **eventual consistency**, достаточную для домена, и поддерживает персональные кабинеты по ролям, рекомендации по интересам и графовое представление связей.

## 1) Общая архитектура

```mermaid
graph TD
    UI["Web-клиент (студент / заказчик / ЦППРП)"]
    API["Backend (Django + DRF, модульный монолит)"]
    DB["Operational DB (SQLite dev / PostgreSQL prod)"]
    OUTBOX["Outbox feed (/api/v1/outbox/events/)"]
    MLS["ML сервис рекомендаций и поиска"]
    GRAPH["Graph projector / graph read model"]
    EXT["Внешние системы (SSO edu.hse.ru, Sheets, LMS/ЕЛК)"]

    UI --> API
    API --> DB
    API --> OUTBOX
    API --> EXT
    OUTBOX --> MLS
    OUTBOX --> GRAPH
    MLS --> DB
```

---

## 2) Потоки / обновление данных и рекомендации

```mermaid
graph TD
    CP["ЦППРП / заказчик обновляет таблицу проектов"]
    SHEET["Google/Yandex Sheets / XLSX"]
    IM["Backend: imports/projects import"]
    PRJ["Operational DB: projects/applications/users"]
    OUTBOX["Outbox feed (project.changed, user_profile.changed, application.changed)"]
    MLS["ML сервис"]
    GRAPH["Graph projector"]
    EMB["ML: индекс проектов (embeddings)"]
    ST["Студент в веб-клиенте"]
    API["Backend: recs/account/users APIs"]

    CP --> SHEET
    SHEET --> IM
    IM --> PRJ
    PRJ --> OUTBOX
    OUTBOX --> MLS
    OUTBOX --> GRAPH
    MLS --> PRJ
    MLS --> EMB

    ST --> API
    API --> MLS
    MLS --> API
```
