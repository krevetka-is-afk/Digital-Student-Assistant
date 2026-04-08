from pathlib import Path
from zipfile import ZipFile

from apps.projects.importers import EXPECTED_HEADERS


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
