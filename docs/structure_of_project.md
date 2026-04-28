# Структура проекта (фактическое состояние)

Актуализировано: 2026-04-29

```txt
Digital-Student-Assistant/
├─ README.md
├─ LICENSE
├─ EVIDENCE/
├─ artifacts/
├─ .github/
│  ├─ workflows/
│  └─ ISSUE_TEMPLATE/
├─ docs/
│  ├─ architecture/
│  │  ├─ adr/
│  │  ├─ contracts/
│  │  └─ permissions.md
│  ├─ csv/
│  ├─ issues/
│  ├─ ops/
│  ├─ runbook/
│  ├─ coursework-docs/
│  ├─ data_source/
│  ├─ espd/
│  ├─ technical-specification/
│  │  └─ technical-specification-3/
│  ├─ 01 General objectives and context of the project.md
│  ├─ 02 Functional requirements.md
│  ├─ 03 NFR.md
│  ├─ 04 Limits.md
│  ├─ 05 Support, development, operation.md
│  ├─ README.md
│  ├─ api_scheme.md
│  ├─ schema_prjects.md
│  └─ structure_of_project.md
├─ infra/
│  ├─ compose/
│  │  └─ test/
│  │     └─ docker-compose.yml
│  ├─ nginx/
│  ├─ observability/
│  ├─ docker-compose.yml
│  ├─ docker-compose.dev.yml
│  ├─ docker-compose.prod.yml
│  └─ docker-compose.staging.yml
├─ perf/
│  └─ k6/
├─ scripts/
│  ├─ backup-postgres.sh
│  ├─ backup-stack.sh
│  ├─ deploy-prod-vm.sh
│  ├─ import-epp-to-vm.sh
│  ├─ install-backup-timer.sh
│  ├─ restore-postgres.sh
│  ├─ run-release-gate.sh
│  ├─ smoke-prod.sh
│  ├─ upload-and-deploy-vm.sh
│  ├─ uv-linters.sh
│  └─ uv-typecheck.sh
├─ security/
│  ├─ seccomp/
│  └─ semgrep/
├─ src/
│  ├─ web/                         # Django + DRF
│  │  ├─ config/
│  │  ├─ apps/
│  │  ├─ client/
│  │  ├─ templates/
│  │  └─ tests/
│  ├─ ml/                          # FastAPI ML service
│  │  ├─ app/
│  │  └─ tests/
│  └─ graph/                       # graph projector service
│     ├─ app/
│     └─ tests/
├─ tests/                          # repository-level tests
│  ├─ contract/
│  ├─ e2e/
│  └─ integration/
├─ pyproject.toml
└─ uv.lock
```

## Основные каталоги

- `docs/` - комплект проектной, архитектурной и учебной документации.
- `src/web/` - основной веб-сервис на Django + DRF.
- `src/ml/` - ML-сервис для поиска и рекомендаций.
- `src/graph/` - сервис проекции данных в графовую модель.
- `tests/` - межсервисные контрактные, интеграционные и e2e-проверки.
- `infra/` - описания окружений, compose-файлы, Nginx и наблюдаемость.
- `scripts/` - эксплуатационные и проверочные сценарии.
- `security/` - конфигурация инструментов анализа безопасности.
- `perf/k6/` - нагрузочные сценарии.

## Django-приложения (`src/web/apps`)

- `account`: ролевые кабинеты и операционные методы API.
- `applications`: домен заявок на проекты.
- `base`: аутентификация, базовые представления, общие разрешения и служебные методы.
- `faculty`: зеркало данных о преподавателях и сопоставление с проектами.
- `frontend`: HTML-интерфейс на Django templates.
- `imports`: импорт входных данных и журнал импортов.
- `outbox`: выдача событий и контрольные точки потребителей.
- `projects`: основной домен проектов и инициативных тем.
- `recs`: шлюз поиска и рекомендаций.
- `search`: поисковые методы.
- `tags`: справочник и обработка тегов.
- `users`: профиль пользователя, интересы и избранное.

## Тестовая структура

- `src/web/apps/<app>/tests/api/` - проверки методов и прав доступа в рамках одного Django-приложения.
- `src/web/apps/<app>/tests/unit/` - изолированные модульные проверки.
- `src/web/tests/` - общие тесты веб-сервиса, затрагивающие несколько приложений.
- `src/ml/tests/` и `src/graph/tests/` - локальные тесты сервисов рекомендаций и графовой проекции.
- `tests/` - проверки на уровне репозитория, включая контракты, интеграцию и e2e.

## Примечания

- `docs/architecture/contracts/` - каноническое место хранения контрактов API, событий и правил доставки outbox.
- `docs/architecture/adr/` - архитектурные решения, принятые по проекту.
- `infra/compose/test/docker-compose.yml` - описание тестового интеграционного контура.
- Подкаталог `docs/technical-specification/technical-specification-3/` хранится как отдельный git-submodule с шаблонами технических заданий.
