# Web Service

`src/web` — основной сервис текущего этапа. Он отвечает за:

- file-native импорт ЭПП из `docs/data_source/EPP.xlsx`
- хранение `EPP` и vacancy-level `Project`
- модерацию проектов и review заявок
- role-based `account` API для `student`, `customer`, `cpprp`

Быстрый локальный цикл:

```bash
uv sync --group dev
uv run python manage.py migrate --settings=config.settings.dev
uv run python manage.py import_epp_xlsx --settings=config.settings.dev
uv run python manage.py runserver --settings=config.settings.dev
```
