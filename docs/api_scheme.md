# Схема API (Canonical v1)

Актуализировано: 2026-04-29

## Точки входа API

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/api/` | Стабильный индекс API со ссылками на версионированные маршруты |
| GET | `/api/schema/` | OpenAPI-схема в машиночитаемом виде |
| GET | `/api/docs/` | Swagger UI для просмотра API-схемы |
| GET | `/api/v1/` | Канонический индекс API v1 |

## Канонический API v1 (`/api/v1/`)

Эти методы используются для ручной проверки, интеграции интерфейса и контроля релизного контракта.

| Метод | Путь | Доступ | Назначение |
|---|---|---|---|
| GET | `/api/v1/health/` | нет | Проверка доступности сервиса |
| GET | `/api/v1/ready/` | нет | Проверка готовности сервиса и связи с базой данных |
| POST | `/api/v1/auth/token/` | нет | Получение DRF-токена по `username/password` |
| GET | `/api/v1/search/?q=<text>` | необязательно | Поиск опубликованных проектов, а для авторизованного пользователя также собственных проектов |
| GET | `/api/v1/initiative-proposals/` | да | Список инициативных тем: автор видит свои, ЦППРП и staff - все |
| POST | `/api/v1/initiative-proposals/` | student/staff | Создание инициативной темы |
| POST | `/api/v1/initiative-proposals/<id>/actions/submit/` | student/staff | Отправка инициативной темы в ЦППРП |
| POST | `/api/v1/initiative-proposals/<id>/actions/moderate/` | cpprp/staff | Модерация инициативной темы (`decision=approve/reject`) |
| GET | `/api/v1/initiative-proposals/<id>/` | да | Получение инициативной темы по идентификатору |
| PUT | `/api/v1/initiative-proposals/<id>/` | student/staff | Полное обновление инициативной темы в редактируемом состоянии |
| PATCH | `/api/v1/initiative-proposals/<id>/` | student/staff | Частичное обновление инициативной темы в редактируемом состоянии |
| DELETE | `/api/v1/initiative-proposals/<id>/` | student/staff | Удаление инициативной темы в редактируемом состоянии |
| GET | `/api/v1/projects/` | необязательно | Список проектов (`page`, `page_size`, `status`, `q`, `ordering`, `staffing_state`, `application_state`, `application_window_state`) |
| POST | `/api/v1/projects/` | да | Создание проекта; владельцем становится текущий пользователь |
| POST | `/api/v1/projects/<id>/actions/submit/` | да | Отправка проекта на модерацию (владелец/staff) |
| POST | `/api/v1/projects/<id>/actions/moderate/` | да | Модерация проекта (`decision=approve/reject`, ЦППРП/staff) |
| GET | `/api/v1/projects/<id>/` | необязательно | Получение проекта по идентификатору |
| PATCH | `/api/v1/projects/<id>/` | да | Обновление проекта (владелец или staff) |
| DELETE | `/api/v1/projects/<id>/` | да | Удаление проекта (владелец или staff) |
| GET | `/api/v1/applications/` | да | Список собственных заявок, а для staff - всех заявок |
| POST | `/api/v1/applications/` | да | Создание заявки; заявителем становится текущий пользователь |
| POST | `/api/v1/applications/<id>/actions/review/` | да | Рассмотрение заявки (`decision=accept/reject`, владелец проекта/staff) |
| GET | `/api/v1/applications/<id>/` | да | Получение заявки по идентификатору |
| PATCH | `/api/v1/applications/<id>/` | да | Обновление заявки (владелец или staff) |
| DELETE | `/api/v1/applications/<id>/` | да | Удаление заявки (владелец или staff) |
| GET | `/api/v1/account/me/` | да | Счетчики и краткая сводка профиля с учетом роли пользователя |
| GET | `/api/v1/account/student/overview/` | student/staff | Обзор кабинета студента с заявками, избранным, сроками и шаблонами |
| GET | `/api/v1/account/customer/projects/` | customer/staff | Список проектов заказчика с полями `applications_count` и `submitted_applications_count` |
| GET | `/api/v1/account/customer/applications/` | customer/staff | Входящие заявки заказчика с поддержкой фильтра `status` |
| GET | `/api/v1/account/cpprp/moderation-queue/` | cpprp/staff | Очередь модерации ЦППРП |
| GET | `/api/v1/account/cpprp/applications/` | cpprp/staff | Обзор заявок для ЦППРП и лента последних изменений (`status` для ленты) |
| GET | `/api/v1/account/cpprp/deadlines/` | cpprp/staff | Список сроков платформы |
| POST | `/api/v1/account/cpprp/deadlines/` | cpprp/staff | Создание срока и публикация события `deadline.changed` |
| GET | `/api/v1/account/cpprp/templates/` | cpprp/staff | Список шаблонов документов |
| POST | `/api/v1/account/cpprp/templates/` | cpprp/staff | Создание шаблона документа |
| GET | `/api/v1/account/templates/<id>/download/` | да | Единая конечная точка скачивания шаблона с учетом роли и аудитории |
| GET | `/api/v1/account/cpprp/export/projects/` | cpprp/staff | Экспорт проектов в CSV |
| GET | `/api/v1/account/cpprp/export/applications/` | cpprp/staff | Экспорт заявок в CSV |
| GET | `/api/v1/users/me/` | да | Получение профиля текущего пользователя |
| PATCH | `/api/v1/users/me/` | да | Обновление профиля текущего пользователя (`role`, `interests`) |
| PUT | `/api/v1/users/me/` | да | Полное обновление профиля текущего пользователя |
| GET | `/api/v1/users/me/favorites/` | да | Список избранных проектов |
| PUT | `/api/v1/users/me/favorites/` | да | Полная замена списка идентификаторов избранных проектов |
| POST | `/api/v1/users/me/favorites/` | да | Добавление идентификаторов проектов в избранное |
| DELETE | `/api/v1/users/me/favorites/<id>/` | да | Удаление проекта из избранного |
| GET | `/api/v1/faculty/persons/` | необязательно | Список актуальных записей о преподавателях НИУ ВШЭ (`q`, `interest`) |
| GET | `/api/v1/faculty/persons/<source_key>/` | необязательно | Получение одной зеркальной записи о преподавателе |
| GET | `/api/v1/faculty/persons/<source_key>/projects/` | необязательно | Список подтвержденных публичных сопоставлений проектов для одного преподавателя |
| GET | `/api/v1/recs/search/?q=<text>` | нет | Поисковый прокси для подсистемы рекомендаций |
| GET | `/api/v1/recs/recommendations/` | да | Персональные рекомендации по интересам и профилю |
| POST | `/api/v1/recs/reindex/` | cpprp/staff | Публикация события `recs.reindex_requested` |
| GET | `/api/v1/imports/epp/` | cpprp/staff | Список запусков импорта |
| POST | `/api/v1/imports/epp/` | cpprp/staff | Запуск импорта XLSX и публикация события `import.completed` при успехе |
| GET | `/api/v1/outbox/events/` | cpprp/staff или служебный токен потребителя | Чтение ленты outbox с семантикой контрольных точек по `consumer` (`mode=poll|replay`,`since_id`,`replay_from_id`) |
| POST | `/api/v1/outbox/events/ack/` | cpprp/staff или служебный токен потребителя | Монотонное подтверждение обработки для контрольной точки потребителя (`consumer`, `event_id`) |
| GET | `/api/v1/outbox/consumers/<consumer>/checkpoint/` | cpprp/staff или служебный токен потребителя | Получение состояния возобновления для потребителя (`last_acked_event_id`, `last_seen_event_id`, `status`) |
| GET | `/api/v1/outbox/snapshot/` | cpprp/staff или служебный токен потребителя | Начальный снимок состояния для внешних потребителей (`watermark`, `projects`, `applications`, `user_profiles`, дополнительные ресурсы faculty) |

## Устаревшие веб-методы

Проект по-прежнему содержит устаревшие неканонические маршруты вне `/api/v1/`.
Они не входят в основной контракт API и не должны использоваться в новых интеграциях:

- `/base/` - устаревшие вспомогательные маршруты base/auth/health;
- `/base/projects/` - устаревшие маршруты проектов;
- `/base/search` - устаревший маршрут поиска;
- `/base/v2/projects/` - устаревший маршрутизатор на viewset.

## Статусы жизненного цикла (I2)

- Проект: `draft -> on_moderation -> published/rejected -> staffed` (+ `archived`)
- Инициативная тема: `draft -> on_moderation -> revision_requested -> on_moderation -> published`
- Заявка: `submitted -> accepted/rejected`
- Прямые переходы между статусами через общий `PATCH` запрещены; нужно использовать специальные методы API.

## Источник истины для релизного контракта

- Обязательные маршруты, операции и компоненты OpenAPI-схемы зафиксированы в `docs/architecture/contracts/api_contract.json`.
- Обязательные типы доменных событий зафиксированы в `docs/architecture/contracts/event_contract.json`.
- Семантика доставки outbox-событий и снимка состояния описана в `docs/architecture/contracts/outbox_delivery_contract.json`.
- `tests/contract/test_openapi_sync.py` проверяет эти требования по сгенерированному `/api/schema/`.
- `tests/contract/test_event_schemas.py` проверяет контракт событий по актуальным вызовам `emit_event(...)` в backend.

## Режимы шлюза рекомендаций

- `semantic`: backend успешно получил ранжированные элементы от внешнего ML-сервиса.
- `keyword-fallback`: backend использовал локальное ранжирование по ключевым словам, потому что ML-сервис недоступен, превысил время ожидания или вернул некорректный ответ.

## Семантика доставки outbox-событий

- Каноническим смещением служит `id` outbox-события.
- Режим `poll`: `GET /api/v1/outbox/events/?consumer=<name>` возвращает события с `id > last_acked_event_id`.
- `ack`: после успешной обработки потребитель подтверждает наибольшее обработанное смещение через `POST /api/v1/outbox/events/ack/`.
- Подтверждение идемпотентно: повторная отправка того же `event_id` не меняет контрольную точку (`ack_status=already_acked`).
- Режим `replay`: `GET /api/v1/outbox/events/?consumer=<name>&mode=replay&replay_from_id=<id>` повторно читает историю с указанного смещения и помечает каждое событие как `acked|pending` относительно текущей контрольной точки.
- После перезапуска потребитель читает `GET /api/v1/outbox/consumers/<consumer>/checkpoint/` и продолжает опрос с сохраненной позиции.

## Быстрая проверка в браузере

1. Откройте `/api/` и убедитесь, что в ответе есть ссылки на `/api/v1/`.
2. Откройте `/api/v1/health/` и проверьте ответ `{"status":"ok"}`.
3. Откройте `/api/v1/ready/` и проверьте ответ `{"status":"ok"}`.
4. Вызовите `POST /api/v1/auth/token/` через DRF browsable API.
5. Передайте токен в заголовке: `Authorization: Token <your_token>`.
6. Откройте `/api/v1/projects/`, `/api/v1/applications/`, `/api/v1/users/me/`.

## Машинная аутентификация потребителей outbox

- Outbox-методы поддерживают служебные токены доступа для сервисов `ml`, `graph` и интеграционных задач, связанных с `faculty`.
- Токены задаются в `OUTBOX_SERVICE_TOKENS` как JSON-объект: `{"ml":"...","graph":"..."}`.
- Пользователи также могут обращаться к outbox-методам через существующие права `cpprp/staff`.

## API зеркала преподавателей

`/api/v1/faculty/*` предоставляет API только для чтения к зеркалу данных преподавателей НИУ ВШЭ и рассчитанным сопоставлениям проектов с научными руководителями, которые хранятся в `apps.faculty`.

- `GET /api/v1/faculty/persons/?q=<text>&interest=<text>` возвращает список актуальных записей о преподавателях.
- `GET /api/v1/faculty/persons/<source_key>/` возвращает одну запись о преподавателе.
- `GET /api/v1/faculty/persons/<source_key>/projects/` возвращает подтвержденные сопоставления с проектами, видимыми в каталоге.

Данные о преподавателях также могут входить в снимок состояния outbox через дополнительные ресурсы: `faculty_persons`, `faculty_publications`, `faculty_courses`, `project_faculty_matches`.

## Политика готовности ML-интеграции

`web` считает внешний ML-сервис пригодным для использования только в том случае, если он возвращает успешный JSON-ответ 2xx с `mode=semantic` и корректным массивом `items` (`project_id`, `score`, `reason`). Во всех остальных случаях - при тайм-ауте, ошибке 5xx, некорректном JSON, неверных элементах или другом режиме - `web` переключается на локальный `keyword-fallback` для текущего запроса.
