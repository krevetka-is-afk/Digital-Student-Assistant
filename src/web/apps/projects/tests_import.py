from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
from zipfile import ZipFile

from apps.projects.importers import EXPECTED_HEADERS, import_epp_xlsx
from apps.projects.models import EPP, Project, ProjectSourceType, ProjectStatus
from apps.projects.transitions import normalize_source_status
from django.contrib.auth import get_user_model


def _xlsx_row(values: list[str]) -> str:
    cells = []
    for value in values:
        escaped = str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        cells.append(f'<c t="inlineStr"><is><t>{escaped}</t></is></c>')
    return f"<row>{''.join(cells)}</row>"


def _build_xlsx(path: Path, rows: list[list[str]]) -> None:
    sheet_rows = "".join(_xlsx_row(row) for row in rows)
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/\
    vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/\
    vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/\
    2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Отчет по вакансиям и темам" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/\
    2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>{sheet_rows}</sheetData>
</worksheet>""",
        )


def _row_from_mapping(mapping: dict[str, str]) -> list[str]:
    return [mapping.get(header, "") for header in EXPECTED_HEADERS]


def _sample_mapping(**overrides) -> dict[str, str]:
    payload = {
        "Номер ЭПП": "10001",
        "Наименование ЭПП": "Data Science EPP",
        "Номер кампании": "cmp-1",
        "Наименование кампании": "Spring 2026",
        "Дата создания вакансии/темы": "2025-10-03T07:43:45Z",
        "Дата старта подачи заявок": "2025-12-09",
        "Дата окончания подачи заявок": "2025-12-16",
        "Дата начала работ": "2026-01-09",
        "Дата окончания работ": "2026-03-31",
        "Статус вакансии/темы": "Опубликована",
        "Дата смены статуса вакансии/темы": "2025-10-03T07:43:45Z",
        "Наименование вакансии": "ML analyst",
        "Наименование вакансии на английском языке": "ML analyst",
        "Тема ВКР/КР": "Forecasting",
        "Тема ВКР/КР на английском языкке": "Forecasting",
        "Язык реализации": "Русский",
        "Тип активности": "Проект",
        "Руководитель вакансии/темы": "Иван Иванов",
        "E-mail руководителя": "ivanov@example.com",
        "Структурное подразделение руководителя": "FCS",
        "Категория персонала руководителя": "staff",
        "Внутренние соруководители вакансии/темы": "Петр Петров",
        'ВКР "Стартап как диплом"': "Нет",
        "Количество мест для подачи заявок": "3",
        "Количество актуальных заявок": "1",
        "Кредиты": "4",
        "Количество часов нагрузки/занятости на студента (в неделю)": "8",
        "Форма контроля": "Зачет",
        "Формат работы": "Онлайн",
        "Формат участия студентов": "Индивидуальный",
        "Формат представления и защиты результатов": "Демо",
        "Формула оценки результатов": "100%",
        "Особенности реализации": "Feature details",
        "Критерии отбора": "Python",
        "Предполагается оплата за участие": "Нет",
        "Возможность пересдач": "Да",
        "Место реализации": "Москва",
        "Внутренний заказчик": "ФКН",
        "Место нахождения внешней организации": "Москва",
        "Внешний заказчик": "ООО Ромашка",
        "ИНН": "1234567890",
        "Тип организации": "Компания",
        "Тип сотрудничества": "Практика",
        "Статус заключения договора о практической подготовке": "Подписан",
        "Номер договора": "42",
        "Дата договора": "2025-10-01",
        "Планируется ли использование ИИ в работе": "Да",
        "Использование Цифровых инструментов": "Jupyter",
        "Области использования": "ML",
        "Библиотеки Python": "pandas, numpy",
        "Методы": "classification",
        "Языки программирования": "Python",
        "Программы и языки программирования для обработки данных и моделирования": "Python",
        "Инструменты и методы для работы с данными": "SQL",
        "Инициатор вакансии/темы": "Инициатор",
        "Тип инициатора": "сотрудник",
        "Теги вакансии": "ml, data",
    }
    payload.update(overrides)
    return payload


def test_import_epp_xlsx_creates_epp_and_project():
    epp_ref = f"10001-{uuid4().hex[:8]}"
    with TemporaryDirectory() as tmp_dir:
        path = Path(tmp_dir) / "EPP.xlsx"
        _build_xlsx(
            path,
            [EXPECTED_HEADERS, _row_from_mapping(_sample_mapping(**{"Номер ЭПП": epp_ref}))],
        )

        stats = import_epp_xlsx(path)

    assert stats.epp_created == 1
    assert stats.projects_created == 1
    epp = EPP.objects.get(source_ref=epp_ref)
    project = Project.objects.get(source_type=ProjectSourceType.EPP, epp=epp)
    assert project.epp_id == epp.id
    assert project.status == ProjectStatus.PUBLISHED
    assert project.status_raw == "Опубликована"
    assert project.raw_payload["Наименование вакансии"] == "ML analyst"
    assert project.tech_tags == ["pandas", "numpy", "classification", "Python", "SQL", "ml", "data"]


def test_normalize_source_status_covers_all_current_values():
    assert normalize_source_status("Создана") == ProjectStatus.CREATED
    assert normalize_source_status("Черновик") == ProjectStatus.DRAFT
    assert normalize_source_status("Доработка инициатором") == ProjectStatus.REVISION_REQUESTED
    assert normalize_source_status("Рассмотрение руководителем") == ProjectStatus.SUPERVISOR_REVIEW
    assert normalize_source_status("Опубликована") == ProjectStatus.PUBLISHED
    assert normalize_source_status("Завершена") == ProjectStatus.COMPLETED
    assert normalize_source_status("Отменена") == ProjectStatus.CANCELLED


def test_import_epp_xlsx_is_idempotent_and_updates_existing_records():
    epp_ref = f"10002-{uuid4().hex[:8]}"
    with TemporaryDirectory() as tmp_dir:
        path = Path(tmp_dir) / "EPP.xlsx"
        initial = _sample_mapping(**{"Номер ЭПП": epp_ref})
        _build_xlsx(path, [EXPECTED_HEADERS, _row_from_mapping(initial)])
        import_epp_xlsx(path)

        updated = _sample_mapping(**{"Номер ЭПП": epp_ref, "Критерии отбора": "Python, SQL"})
        _build_xlsx(path, [EXPECTED_HEADERS, _row_from_mapping(updated)])
        stats = import_epp_xlsx(path)

    assert stats.projects_updated == 1
    assert (
        Project.objects.filter(source_type=ProjectSourceType.EPP, epp__source_ref=epp_ref).count()
        == 1
    )
    project = Project.objects.get(source_type=ProjectSourceType.EPP, epp__source_ref=epp_ref)
    assert project.selection_criteria == "Python, SQL"


def test_import_epp_xlsx_preserves_local_locked_status():
    epp_ref = f"10003-{uuid4().hex[:8]}"
    with TemporaryDirectory() as tmp_dir:
        path = Path(tmp_dir) / "EPP.xlsx"
        _build_xlsx(
            path,
            [EXPECTED_HEADERS, _row_from_mapping(_sample_mapping(**{"Номер ЭПП": epp_ref}))],
        )
        import_epp_xlsx(path)

        project = Project.objects.get(source_type=ProjectSourceType.EPP, epp__source_ref=epp_ref)
        project.status = ProjectStatus.ON_MODERATION
        project.save(update_fields=["status", "updated_at"])

        updated = _sample_mapping(**{"Номер ЭПП": epp_ref, "Статус вакансии/темы": "Завершена"})
        _build_xlsx(path, [EXPECTED_HEADERS, _row_from_mapping(updated)])
        stats = import_epp_xlsx(path)

    project.refresh_from_db()
    assert stats.warnings == 1
    assert project.status == ProjectStatus.ON_MODERATION
    assert project.status_raw == "Завершена"


def test_project_source_constraint_skips_blank_manual_source_ref():
    user = get_user_model().objects.create_user(
        username=f"manual-owner-{uuid4().hex[:8]}",
        password="pass-123",
    )
    first = Project.objects.create(title="Manual one", owner=user)
    second = Project.objects.create(title="Manual two", owner=user)

    assert first.source_ref == ""
    assert second.source_ref == ""
    assert Project.objects.filter(source_type=ProjectSourceType.MANUAL).count() >= 2
