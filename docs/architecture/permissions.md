# Матрица прав доступа API

Документ фиксирует матрицу авторизации по ролям продукта для API-first итерации MVP.

## Источник истины

- Роль продукта хранится в `apps.users.models.UserProfile.role`.
- Поддерживаемые роли: `student`, `customer`, `cpprp`.
- Пользователь `Django staff` сохраняет административный обход ограничений для перечисленных ниже методов.

## Матрица ролей

| API surface | Student | Customer | CPPRP | Staff |
| --- | --- | --- | --- | --- |
| `GET /api/v1/projects/`, `GET /api/v1/projects/{id}/` | Только каталог; после входа также видны собственные приватные черновики | Каталог и собственные приватные черновики | Каталог и, при наличии, собственные приватные черновики | Полная видимость в рамках поведения staff |
| `POST /api/v1/projects/` | Запрещено | Разрешено | Запрещено | Разрешено |
| `PATCH/PUT/DELETE /api/v1/projects/{id}/` | Запрещено | Разрешено только для собственных проектов | Запрещено | Разрешено |
| `POST /api/v1/projects/{id}/actions/submit/` | Запрещено | Разрешено только для собственных проектов | Запрещено | Разрешено |
| `POST /api/v1/projects/{id}/actions/moderate/` | Запрещено | Запрещено | Разрешено | Разрешено |
| `GET/POST /api/v1/applications/` | Разрешено только для собственных заявок | Запрещено | Запрещено | Разрешено |
| `GET/PATCH/DELETE /api/v1/applications/{id}/` | Разрешено только для собственных заявок | Запрещено | Запрещено | Разрешено |
| `POST /api/v1/applications/{id}/actions/review/` | Запрещено | Разрешено только для заявок на собственные проекты | Запрещено | Разрешено |
| `GET /api/v1/account/student/overview/` | Разрешено | Запрещено | Запрещено | Разрешено |
| `GET /api/v1/account/customer/projects/`, `GET /api/v1/account/customer/applications/` | Запрещено | Разрешено | Запрещено | Разрешено |
| `GET /api/v1/account/cpprp/*` | Запрещено | Запрещено | Разрешено | Разрешено |
| `GET/POST /api/v1/imports/epp/` | Запрещено | Запрещено | Разрешено | Разрешено |
| `POST /api/v1/recs/reindex/` | Запрещено | Запрещено | Разрешено | Разрешено |

## Замечания по реализации

- Проверка прав на уровне методов API реализована в `apps.account.permissions` через переиспользуемые классы DRF:
  `IsStudentOrStaff`, `IsCustomerOrStaff`, `IsCpprpOrStaff`.
- Ограничения на уровне доменной логики дублируют ту же матрицу, если бизнес-логика вызывается вне маршрута API:
  `apps.projects.transitions.submit_project_for_moderation`,
  `apps.applications.transitions.review_application`.
- Критичные отказы в доступе к CPPRP/staff-only методам журналируются из `apps.account.permissions`.

## Связанные файлы и тесты

- Права и переходы проектов:
  `src/web/apps/projects/views.py`,
  `src/web/apps/projects/transitions.py`,
  `src/web/apps/projects/tests/api/test_projects_api.py`,
  `src/web/apps/projects/tests/api/test_transitions.py`.
- Права и переходы заявок:
  `src/web/apps/applications/views.py`,
  `src/web/apps/applications/transitions.py`,
  `src/web/apps/applications/tests/api/test_transitions.py`.
- Кабинеты и операционные методы:
  `src/web/apps/account/views.py`,
  `src/web/apps/account/tests/api/test_account_api.py`,
  `src/web/apps/imports/views.py`,
  `src/web/apps/imports/tests/api/test_import_api.py`,
  `src/web/apps/recs/views.py`,
  `src/web/apps/recs/tests/api/test_recs_api.py`.
