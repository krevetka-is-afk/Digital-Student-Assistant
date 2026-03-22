# EPP Account Workflow

## Canonical source

Текущая каноническая схема исходит из файла `docs/data_source/EPP.xlsx`.

- `EPP` — родительская сущность в `projects`
- `Project` — vacancy/topic строка из XLSX
- `Application` — заявка студента на vacancy-level `Project`

Сырые данные сохраняются без потерь:

- `EPP.raw_payload` хранит EPP-level source payload
- `Project.raw_payload` хранит полную source row
- `status_raw` сохраняет исходный статус из файла

## Status normalization

Нормализация source status:

- `Создана` -> `created`
- `Черновик` -> `draft`
- `Доработка инициатором` -> `revision_requested`
- `Рассмотрение руководителем` -> `supervisor_review`
- `Опубликована` -> `published`
- `Завершена` -> `completed`
- `Отменена` -> `cancelled`

Публичный каталог показывает только `published` и `staffed`.

Локальный workflow использует дополнительно:

- `on_moderation`
- `rejected`
- `archived`

Если импортируемый проект уже находится в одном из локально-управляемых статусов `on_moderation`, `rejected`, `staffed`, импорт сохраняет `status_raw`, но не перезаписывает локальный `status`.

## Account API

`/api/v1/account/` предоставляет:

- `me/`
- `student/overview/`
- `customer/projects/`
- `customer/applications/`
- `cpprp/moderation-queue/`
- `cpprp/applications/`

`account` агрегирует существующие доменные сущности и не заменяет `/api/v1/projects/` и `/api/v1/applications/`.

## Out of scope

- SSR UI
- вузовский SSO
- расширение `src/ml`
- расширение `src/graph`
