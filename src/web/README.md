# Web Service

`src/web` — основной сервис текущего этапа. Он отвечает за:

- file-native импорт ЭПП из `docs/data_source/EPP.xlsx` или из явно переданного `--path`
- хранение `EPP` и vacancy-level `Project`
- модерацию проектов и review заявок
- role-based `account` API для `student`, `customer`, `cpprp`
- outbox/recommendation integration surfaces для downstream `graph`/`ml`

Быстрый локальный цикл:

```bash
uv sync --group dev
uv run python manage.py migrate --settings=config.settings.dev
uv run python manage.py import_epp_xlsx --settings=config.settings.dev
uv run python manage.py runserver --settings=config.settings.dev
```
