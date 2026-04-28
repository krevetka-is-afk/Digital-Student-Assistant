# 2. Функциональные требования

Актуализировано: 2026-04-28.

## Student

- Регистрация, вход и подтверждение email.
- Просмотр каталога опубликованных проектов.
- Поиск, фильтрация, сортировка и просмотр карточки проекта.
- Управление профилем, научными интересами и избранными проектами.
- Получение рекомендаций через `recs` facade.
- Подача заявки на проект и просмотр статуса своих заявок.
- Доступ к документам/шаблонам, опубликованным для соответствующей аудитории.

## Customer

- Создание и редактирование собственных проектов.
- Отправка проекта на модерацию.
- Просмотр собственных проектов и их статусов.
- Просмотр входящих заявок на собственные проекты.
- Принятие или отклонение заявок студентов в допустимых статусах.

## CPPRP / Staff

- Просмотр очереди модерации.
- Публикация, отклонение или возврат проектов по action endpoints.
- Управление дедлайнами и шаблонами документов.
- Просмотр административных сводок по проектам и заявкам.
- Экспорт проектов и заявок в CSV.
- Запуск импорта EPP XLSX.
- Запуск `recs.reindex_requested` через API.

## Project and application workflow

- Project: `draft -> on_moderation -> published/rejected -> staffed`, также поддерживается `archived`.
- Initiative proposal: `draft -> on_moderation -> revision_requested -> on_moderation -> published`.
- Application: `submitted -> accepted/rejected`.
- Прямое изменение lifecycle-статусов через generic `PATCH` запрещено; переходы выполняются через action endpoints.

## Import

- Канонический runtime-контракт импорта: `POST /api/v1/imports/epp/` с XLSX-файлом.
- CLI-команда `import_epp_xlsx` поддерживается для локального и bootstrap-сценариев.
- `ImportRun.stats` фиксирует результат импорта.

## Recommendations, ML and graph

- `web` вызывает ML через thin REST gateway (`/search`, `/recommendations`, `/reindex`).
- Если ML не возвращает валидный `mode=semantic`, `web` использует локальный keyword fallback.
- Downstream-сервисы получают изменения через outbox events, ack/checkpoint/replay и snapshot.
- Graph service строит Neo4j-проекцию из outbox events.

## Faculty

- Система хранит зеркало faculty persons, publications, courses.
- Для проектов рассчитываются project-faculty matches по данным научного руководителя.
- Read-only API: `/api/v1/faculty/persons/`, `/api/v1/faculty/persons/<source_key>/`, `/api/v1/faculty/persons/<source_key>/projects/`.
