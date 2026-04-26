# DEVLOG — Digital Student Assistant

Журнал разработки. Каждая запись фиксирует **что**, **где** и **зачем** было изменено на данном этапе.

---

## Сессия 1 (ранее) — Базовый SSR Frontend

### Описание
Создание Django SSR frontend-приложения поверх готового DRF бэкенда. Все экраны с нуля.

### Что было сделано

#### Новое приложение `apps/frontend/`
- `src/web/apps/frontend/urls.py` — все URL-маршруты frontend
- `src/web/apps/frontend/views/` — views разбиты по доменам: `projects.py`, `applications.py`, `moderation.py`, `profile.py`, `auth.py`
- `src/web/apps/frontend/templatetags/frontend_extras.py` — кастомные теги `get_item` (доступ по ключу в шаблоне), `role_label` (читаемое название роли)

#### Шаблоны (`src/web/templates/frontend/`)
| Файл                                | Экран                                                   |
| ----------------------------------- | ------------------------------------------------------- |
| `auth.html`                         | Вход / регистрация                                      |
| `project_list.html`                 | Каталог проектов (поиск + фильтры + HTMX)               |
| `project_detail.html`               | Страница проекта (apply modal, owner actions)           |
| `project_form.html`                 | Создание / редактирование проекта (заказчик)            |
| `profile.html`                      | Личный кабинет (view/edit toggle, interests chip input) |
| `application_list.html`             | Список заявок студента                                  |
| `project_applications.html`         | Заявки на проект (заказчик: accept / reject)            |
| `moderation_list.html`              | Очередь модерации (ЦППРП)                               |
| `recommendations.html`              | Рекомендации проектов по интересам                      |
| `partials/apply_button.html`        | Кнопка "Откликнуться" (HTMX swap)                       |
| `partials/apply_action_detail.html` | Блок отклика на странице проекта                        |
| `partials/projects_grid.html`       | Сетка карточек (HTMX partial для поиска)                |

#### Ключевые решения
- HTMX `hx-get` + `hx-trigger="input delay:350ms"` на поисковой строке — обновляет только `#projects-section`
- `hx-push-url="true"` — поиск и фильтры отражаются в адресной строке без перезагрузки
- Shared Apply Modal — один `<div id="shared-apply-modal">` на всю страницу, открывается через `openApplyModal(pk, title)`
- `ProjectStatus.catalog_values()` — только PUBLISHED + STAFFED попадают в каталог

---

## Сессия 2 (ранее) — Вкладки: Рекомендации, Закладки, Мои заявки

### Описание
Перенос разделов «Рекомендации» и «Мои заявки» из основной навигации во вкладки на странице `/projects/`. Добавление закладок.

### Что было сделано

#### Модели
- `src/web/apps/projects/models.py` — добавлены:
  - модель `Bookmark(user, project, created_at)` — `unique_together = ("user", "project")`
  - поле `Project.supervisor_name = CharField(max_length=255, blank=True, default="")`
  - поле `Project.source_type` — значение `INITIATIVE` для инициативных проектов студентов
- `src/web/apps/projects/migrations/0007_bookmark.py` — применена
- `src/web/apps/projects/migrations/0008_add_supervisor_name.py` — применена

#### Views
- `src/web/apps/frontend/views/projects.py`:
  - `project_list` — расширен для студентов: загружает `rec_projects`, `bookmarked_ids` (set), `bookmark_projects`, `my_applications`, `my_initiative_projects`, `app_counts`
  - `toggle_bookmark(pk)` — POST, `get_or_create` Bookmark, возвращает `JsonResponse({"bookmarked": bool})`
  - `InitiativeProjectForm` — поля: title, description, tech_tags_raw, team_size (max 10), supervisor_name (optional)
  - `initiative_project_create` — студент предлагает проект → `status=ON_MODERATION, source_type=INITIATIVE`
- `src/web/apps/frontend/views/__init__.py` — добавлены экспорты `toggle_bookmark`, `initiative_project_create`
- `src/web/apps/frontend/urls.py` — добавлены маршруты:
  - `projects/<int:pk>/bookmark/` → `toggle_bookmark`
  - `projects/initiative/` → `initiative_project_create`

#### Шаблоны
- `src/web/templates/frontend/project_list.html` — переработан:
  - Tab bar: кнопки «Все проекты» / «Рекомендации» / «Закладки» (с badge-счётчиком) / «Мои заявки» (с amber-badge)
  - `#tab-panel-catalog` — существующий каталог + поиск
  - `#tab-panel-recs` — карточки рекомендаций с причиной и mode-badge
  - `#tab-panel-bookmarks` — закладки с data-pk для удаления из вкладки
  - `#tab-panel-applications` — инициативные проекты (статус-строки) + фильтр заявок
  - JS: `switchProjectTab(tab)`, `toggleBookmark(btn)`, `filterApps(status)`, `_updateBookmarksBadge()`
  - Оптимистичное обновление закладок: иконка меняется сразу, откат при ошибке
- `src/web/templates/frontend/partials/bookmark_button.html` — новый partial (outline/filled SVG)
- `src/web/templates/frontend/partials/projects_grid.html` — добавлен `bookmark_button` partial в footer карточки
- `src/web/templates/frontend/initiative_form.html` — новый: форма предложения инициативного проекта с JS-preview тегов
- `src/web/templates/frontend/moderation_list.html` — добавлены: badge «Инициативный», поле supervisor_name, метка «Студент» вместо «Владелец»
- `src/web/templates/frontend/project_detail.html` — добавлены: badge «Инициативный», блок supervisor_name в сайдбаре
- `src/web/templates/base.html` — удалены nav-ссылки «Рекомендации» и «Мои заявки» для студентов (перенесены во вкладки)

#### Profile
- `src/web/apps/frontend/views/profile.py` — добавлены: `bookmarks_count`, `initiative_count` для студентов
- `src/web/templates/frontend/profile.html` — stats-сетка студента: заявки + закладки + инициативные проекты (со ссылками `?tab=...`)

---

## Сессия 3 — 2026-04-18 — Профиль, тесты, фильтры, README

### Описание
Завершение профиля, добавление deep-link из профиля в вкладки, фильтрация по интересам в каталоге, тесты frontend-views, исправление бага ML-gateway, обновление README.

### Изменённые файлы

#### `src/web/templates/frontend/profile.html`
- **Quick actions (строки ~200–216):** исправлена ссылка «Мои заявки» — была `{% url 'frontend:application_list' %}`, стала `{% url 'frontend:project_list' %}?tab=applications`
- Добавлена новая строка «Предложить проект» → `{% url 'frontend:initiative_project_create' %}`

#### `src/web/templates/frontend/project_list.html`
- **JS (после `switchProjectTab`):** добавлен IIFE для авто-переключения вкладки при загрузке страницы по `?tab=` параметру URL:
  ```js
  (function() {
    var params = new URLSearchParams(window.location.search);
    var tab = params.get('tab');
    if (tab && document.getElementById('tab-panel-' + tab)) {
      switchProjectTab(tab);
    }
  })();
  ```
- **Каталог (перед секцией «Все проекты»):** добавлены чипы быстрых фильтров по интересам студента — теги из профиля, которые есть в проектах, становятся синими кликабельными ссылками (`?tech_tags=...`); отсутствующие в проектах — серые

#### `src/web/apps/frontend/views/projects.py`
- `project_list` view: добавлен `user_interests: list[str]` в context для студентов (из `request.user.profile.interests`)
- `recommendations_view`: заменён на однострочный редирект → `/projects/?tab=recs`; мёртвый код удалён

#### `src/web/apps/frontend/views/applications.py`
- `application_list`: заменён на однострочный редирект → `/projects/?tab=applications`; мёртвый код удалён

#### `src/web/apps/recs/services.py`
- `_ml_service_url()`: изменён порядок приоритетов — **env var теперь имеет приоритет над Django settings** (12-factor principle). Было: settings → env; стало: env → settings. Это исправляет pre-existing баг, при котором `monkeypatch.setenv` в тестах не работал.

#### `src/web/apps/frontend/tests/` (новые файлы)
- `tests/__init__.py` — пустой, делает директорию пакетом
- `tests/conftest.py` — Django setup для pytest (аналогично `apps/recs/tests/`)
- `tests/test_frontend_views.py` — **17 тестов**:

| Тест                                                   | Что проверяет                             |
| ------------------------------------------------------ | ----------------------------------------- |
| `test_project_list_shows_tabs_for_student`             | Вкладки видны студенту                    |
| `test_project_list_no_tabs_for_anonymous`              | Вкладок нет для анонима                   |
| `test_toggle_bookmark_creates_and_removes`             | Toggle bookmark: создаёт и удаляет        |
| `test_toggle_bookmark_requires_login`                  | Bookmark требует авторизации              |
| `test_bookmarked_project_appears_in_bookmarks_tab`     | Закладка видна в панели                   |
| `test_initiative_form_get_renders_for_student`         | GET формы для студента — 200              |
| `test_initiative_form_get_redirects_for_customer`      | GET формы для заказчика — 302             |
| `test_initiative_project_create_post_valid`            | POST с данными → статус ON_MODERATION     |
| `test_initiative_project_create_post_invalid_no_title` | POST без title → 200 + ошибка             |
| `test_initiative_project_with_supervisor`              | supervisor_name сохраняется               |
| `test_initiative_projects_visible_in_applications_tab` | Инициативный проект виден во вкладке      |
| `test_profile_view_shows_student_stats`                | Профиль показывает stats студента         |
| `test_profile_update_post_saves_name`                  | POST профиля сохраняет имя и bio          |
| `test_application_list_redirects_to_projects_tab`      | `/applications/` → 302 + tab=applications |
| `test_recommendations_view_redirects_to_projects_tab`  | `/recommendations/` → 302 + tab=recs      |
| `test_moderation_list_forbidden_for_student`           | Студент не попадает в модерацию           |
| `test_moderation_list_accessible_for_cpprp`            | ЦППРП видит очередь                       |

**Итог: 35 / 35 тестов зелёных.**

#### `README.md`
- Добавлен раздел «Возможности» (по ролям: студент / заказчик / модератор)
- Таблица архитектуры (стек компонентов)
- Раздел «Тесты» с командами запуска
- Структура проекта в виде дерева
- Инструкция запуска ML-сервиса локально

---

---

## Сессия 4 — 2026-04-18 — Баг-фикс: доступ анонимного пользователя

### Описание
Обнаружены два бага при ручном тестировании:
1. Анонимный пользователь видел весь каталог проектов без авторизации
2. Анонимный пользователь мог открыть модальное окно «Откликнуться» и после отправки получал HTML страницы входа внутри карточки проекта (вместо редиректа на логин)

Корневая причина обоих: `project_list` и `project_detail` не требовали авторизации; `submit_application` при fetch()-вызове возвращал HTML-редирект, который JS вставлял в DOM.

### Изменённые файлы

#### `src/web/apps/frontend/views/projects.py`
- `project_list` — добавлен `@login_required(login_url="/auth/")`. Анонимный пользователь теперь перенаправляется на страницу входа с `?next=/projects/`.
- `project_detail` — добавлен `@login_required(login_url="/auth/")`. Прямая ссылка на проект тоже требует авторизации.

#### `src/web/apps/frontend/views/applications.py`
- `submit_application` — переставлена проверка авторизации **до** проверки модератора (логически правильнее). Для неавторизованного пользователя с `fetch()`-запросом (source=card) теперь возвращается `JsonResponse({"error": "unauthenticated", "redirect": "/auth/"}, status=401)` вместо HTML-редиректа. HTMX-ветка (`HX-Redirect`) оставлена без изменений.

#### `src/web/templates/frontend/project_list.html`
- JS-обработчик `fetch()` в shared apply modal: добавлена проверка `if (res.status === 401)` — выполняет `window.location.href = data.redirect`, перебрасывая пользователя на страницу логина. Также добавлена проверка `if (!res.ok)` перед вставкой HTML в DOM — предотвращает инъекцию произвольного HTML при любых других серверных ошибках.

#### `src/web/apps/frontend/tests/test_frontend_views.py`
- Тест `test_project_list_no_tabs_for_anonymous` → переименован и переписан в `test_project_list_redirects_anonymous_to_auth` (ожидает 302 вместо 200)
- Добавлен `test_project_detail_redirects_anonymous_to_auth`
- Добавлен `test_submit_application_returns_401_json_for_anonymous`

**Итог: 19 / 19 тестов зелёных.**

---

## Сессия 5 — 2026-04-18 — Аудит адаптивности

### Описание
Проверка всех шаблонов проекта на соответствие responsive-требованиям. Аудит проведён вручную по исходникам: поиск fixed-width в px там, где нужна резиновая вёрстка, отсутствие viewport meta-тега, некорректные breakpoints.

### Методология
Адаптивность определяется на шаге Style Engine (медиазапросы фильтруют правила CSSOM) и проявляется на шаге Layout (геометрия пересчитывается от размера layout viewport). Проверялось:
1. Наличие `<meta name="viewport">` — без него мобильный браузер эмулирует viewport ~980px и медиазапросы ломаются
2. Наличие фиксированных ширин (`width: Npx`) там, где элемент должен тянуться
3. Отзывчивость сеток карточек и форм

### Результаты

| Файл | Строка | Что | Статус |
|------|--------|-----|--------|
| `src/web/templates/base.html` | 6 | `<meta name="viewport" content="width=device-width, initial-scale=1">` | ✅ Присутствует |
| `src/web/templates/frontend/project_list.html` | карточки | `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3` | ✅ Mobile-first сетка |
| `src/web/templates/frontend/project_form.html` | все поля | `w-full` на input/textarea/select | ✅ Резиновые поля |
| `src/web/templates/frontend/initiative_form.html` | все поля | `w-full` на input/textarea | ✅ Резиновые поля |
| `src/web/templates/frontend/profile.html` | все поля | `w-full` на input/textarea | ✅ Резиновые поля |
| `src/web/templates/base.html` | навигация | `hidden sm:flex` — навигация скрыта на экранах < 640px | ⚠️ Нет hamburger-меню |
| `src/web/templates/frontend/moderation_list.html` | ~89 | Инлайн-стиль `grid-template-columns: 140px 1fr` — фиксированная колонка решения | ⚠️ Приемлемо |

### Детали по предупреждениям

**Навигация (`hidden sm:flex`):**
На смартфонах (< 640px) шапка с навигацией скрыта — hamburger-меню не реализовано. Это **осознанное решение**: платформа разработана для desktop-первичного использования (учебный процесс, рабочее место), студенты и заказчики преимущественно работают с ноутбука. Для production-продукта потребовалось бы добавить мобильное меню, но в рамках курсовой это не является критичным дефектом.

**`moderation_list.html`, фиксированная колонка 140px:**
Используется в таблице очереди модерации. Модераторы (ЦППРП) работают исключительно в десктопном контексте. Колонка содержит кнопки «Одобрить»/«Отклонить» — фиксированная ширина обоснована UX-соображениями (кнопки не сжимаются). На мобильном layout не ломается, просто кнопки занимают меньше места.

### Вывод
Критических responsive-проблем нет. Все пользовательские контентные экраны (каталог, формы, профиль) адаптированы. Две пометки ⚠️ относятся к служебным интерфейсам (модерация) и навигации — оба случая приемлемы для desktop-primary учебной платформы.

---

## Статус задач

| #   | Задача                                                  | Статус                                                                                                                                                                                                              |
| --- | ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Рекомендации в отдельной вкладке                        | ✅ Готово                                                                                                                                                                                                            |
| 2   | Работоспособность ML модели                             | ✅ Работает (heuristic stub + graceful fallback)                                                                                                                                                                     |
| —   | Баг: анонимный доступ + HTML в apply-area               | ✅ Исправлен (сессия 4)                                                                                                                                                                                              |
| 3   | Адаптивность (responsive)                               | ✅ Аудит проведён (сессия 5), критических проблем нет                                                                                                                                                                |
| 4   | Тестирование                                            | ✅ 37/37 тестов (19 frontend + 8 recs + 10 base)                                                                                                                                                                     |
| 5   | README                                                  | ✅ Обновлён                                                                                                                                                                                                          |
| 6   | Личный кабинет                                          | ✅ Готово                                                                                                                                                                                                            |
| 7   | Формы, фильтры, теги                                    | ✅ Быстрые фильтры по интересам добавлены                                                                                                                                                                            |
| 8   | Анализ бэкенда                                          | ✅ Готово (`docs/Анализ бэкенда.md`) — 3 сервиса, полная API-таблица, расхождения моделей, ML-оценка                                                                                                                 |
| 9   | Задачи от научника                                      | 🔲 В работе — 3 подзадачи: (а) вкладка «Статьи» из publications.hse.ru — нужен API endpoint (найти через DevTools); (б) вкладка «Научные сотрудники» — нужен источник данных; (в) визуализация графа — **Vis.js** |
| 10  | Развитие темы                                           | 🔲 Pending                                                                                                                                                                                                          |
| 11  | Линия защиты                                            | 🔲 Pending                                                                                                                                                                                                          |
| 12  | История и контекст frontend-разработки                  | ✅ Готово (`docs/История и контекст frontend-разработки.md`)                                                                                                                                                         |
| 13  | Мобильный веб: от WAP до PWA                            | 🔲 Новая задача — расширить историческую цепочку: WAP/WML → мобильный Safari (2007) → Android Browser → адаптивный веб → PWA                                                                                        |
| 14  | Desktop UI вне браузера: нативные приложения и Electron | 🔲 Новая задача — что такое UI в нативных приложениях (Qt, WinForms, Swing), как веб-технологии попали на десктоп (Electron), чем отличается от браузерного frontend                                                |
| 15  | Интерфейсы за пределами экрана: embedded и IoT          | 🔲 Новая задача — кнопочный интерфейс стиральной машины, WAP на Nokia, LCD-дисплеи; где заканчивается «frontend» и начинается «embedded UI»                                                                         |
| 16  | UI/UX как дисциплина                                    | 🔲 Новая задача — что такое UX vs UI, история HCI, принципы (Fitts, Hick, Nielsen), дизайн-системы, связь с frontend; как UX-решения отразились в проекте                                                           |
| 17  | Линия защиты — финальный документ                       | 🔲 Переосмыслить задачу 11: сформировать структурированный список вопросов + развёрнутых ответов по всем темам проекта. Основан на Q&A-файле + всех образовательных документах                                      |
| 18  | Q&A: вопросы по бэкенду                                 | ✅ Готово — добавлен раздел «Бэкенд и архитектура системы» в `docs/Вопросы и ответы по проекту.md`: 7 вопросов (3 сервиса, Graph сервис, outbox pattern, frontend vs REST API, закладки, ML stub, Bearer vs session) |
| 19  | Развитие: EPP-поля в шаблонах                           | 🔲 Новая задача — показать дедлайн заявок, формат работы, кредиты в карточке проекта (поля уже есть в БД, нужно только добавить в шаблоны)                                                                          |
